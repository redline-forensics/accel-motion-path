import maya.OpenMaya as OpenMaya
import maya.OpenMayaMPx as OpenMayaMPx
import maya.cmds as cmds


# The base class for the command which will create our accelMotionPath
class CreateAccelMotionPath(OpenMayaMPx.MPxCommand):
    # Required initialization
    def __init__(self):
        OpenMayaMPx.MPxCommand.__init__(self)

    # The stuff that executes when this command is run
    def doIt(self, argsList):
        # Create a motionPath and accelMotionPath
        motionPath = cmds.pathAnimation(fractionMode=True, follow=True, followAxis="x", upAxis="y",
                                        worldUpType="vector", worldUpVector=[0, 1, 0], inverseUp=False,
                                        inverseFront=False, bank=False, startTimeU=1, endTimeU=30)
        accelMotionPath = cmds.createNode("accelMotionPath")

        # Connect accelMotionPath's u-value output to motionPath's u-value input
        cmds.disconnectAttr(motionPath + "_uValue.output", motionPath + ".uValue")
        cmds.connectAttr(accelMotionPath + ".uValue", motionPath + ".uValue")

        # Generate an info node on the base curve of the motion path so we can find out the arc length
        curve = cmds.listConnections(motionPath, type="curveShape")
        curveInfo = cmds.arclen(curve, constructionHistory=True)

        # Connect the arc length output to accelMotionPath's arc length input
        cmds.connectAttr(curveInfo + ".arcLength", accelMotionPath + ".arcLength")

        # Connect the time node to accelMotionPath's time input so we know what frame we're on
        cmds.connectAttr("time1.outTime", accelMotionPath + ".time")

        # Select the accelMotionPath for the user for convenience
        cmds.select(accelMotionPath)


# Creator for the createAccelMotionPath command (above)
def createAccelMotionPathCreator():
    return OpenMayaMPx.asMPxPtr(CreateAccelMotionPath())


# The actual node class for our accelMotionPath
class AccelMotionPath(OpenMayaMPx.MPxNode):
    # Creates a required local identifier for this plugin node
    kPluginNodeId = OpenMaya.MTypeId(0x00000001)

    # Initialize attributes
    timeInit = OpenMaya.MObject()  # Time to start motion (in frames)
    time = OpenMaya.MObject()  # Current time (in frames)
    timeLast = OpenMaya.MObject()  # Previous time (in frames) [utility]
    posInit = OpenMaya.MObject()  # Object's position along the curve to start at (in ft)
    velInit = OpenMaya.MObject()  # Object's initial velocity (in ft/s)
    vel = OpenMaya.MObject()  # Object's current velocity (in ft/s)
    killVel = OpenMaya.MObject()  # Velocity at which to stop object's motion to prevent moving backwards (in ft/s)
    accel = OpenMaya.MObject()  # Object's current acceleration (in ft/s/s)
    u = OpenMaya.MObject()  # Object's current u-value/fractional distance along the curve
    uLast = OpenMaya.MObject()  # Previous u-value [utility]
    arcLen = OpenMaya.MObject()  # Length of the base curve of the motion path (in ft)
    dist = OpenMaya.MObject()  # Object's current distance along the curve from the starting position (in ft)

    def __init__(self):
        OpenMayaMPx.MPxNode.__init__(self)

    def compute(self, plug, data):
        if plug == AccelMotionPath.u:  # We are updating the u-value
            arcLen = data.inputValue(AccelMotionPath.arcLen).asFloat()  # Get arc length attribute
            posInit = data.inputValue(AccelMotionPath.posInit).asFloat()  # Get initial position attribute

            # Check the current time
            time = data.inputValue(AccelMotionPath.time).asFloat()  # Get current time attribute
            timeInit = data.inputValue(AccelMotionPath.timeInit).asFloat()  # Get start time attribute
            if time <= timeInit:  # The current time is lower than the user-set motion start time
                u = float(posInit) / arcLen  # Set new u-value to the user-set initial position

                lastTime = timeInit  # Set the last time utility attribute to be the user-set motion start time

                velInit = data.inputValue(AccelMotionPath.velInit).asFloat()  # Get initial velocity attribute
                vel = velInit  # Set the new velocity to the user-set initial velocity
            else:  # The current time is above the start time
                uLast = data.inputValue(AccelMotionPath.uLast).asFloat()  # Get last u-value attribute

                # Check if the object's velocity is below the user-set kill velocity
                velLast = data.inputValue(AccelMotionPath.vel).asFloat()  # Get last velocity attribute
                killVel = data.inputValue(AccelMotionPath.killVel).asFloat()  # Get kill velocity attribute
                if velLast <= killVel:  # The velocity is below the kill velocity
                    vel = 0.0  # Set the new velocity to 0
                    u = uLast  # Set the new u-value to the last u-value (i.e. keep the object in the same place)
                else:  # The velocity is above the kill velocity
                    # Set new u-value based on kinematics calculation
                    accel = data.inputValue(AccelMotionPath.accel).asFloat()
                    timeLast = data.inputValue(AccelMotionPath.timeLast).asFloat()
                    deltaT = time - timeLast
                    fps = getFPS()
                    pos = uLast * arcLen + float(velLast) / fps * deltaT + 0.5 * float(accel) / fps ** 2 * deltaT ** 2
                    u = float(pos) / arcLen

                    if u > 1.0:
                        vel = velLast
                    else:
                        if u < 0.0:
                            u = 0.0
                        vel = velLast + accel * deltaT

                lastTime = time  # Set the last time utility attribute to the current time

            # Calculate distance based on newly calculated position
            if u >= 1.0:  # The u-value is at or past the end of the curve
                dist = arcLen - posInit  # Just set the distance to be the arc length minus the user-set initial pos
            elif u <= 0.0:  # The u-value is at or before the beginning of the curve
                dist = posInit  # Just set the distance to be the user-set initial position
            else:  # The u-value is somewhere in the middle of the curve
                dist = (u * arcLen) - posInit  # Set the distance to the position along the curve minus the initial pos

            # Update our changed attributes with Maya
            data.outputValue(AccelMotionPath.u).setFloat(u)
            data.outputValue(AccelMotionPath.vel).setFloat(vel)
            data.outputValue(AccelMotionPath.timeLast).setFloat(lastTime)
            data.outputValue(AccelMotionPath.uLast).setFloat(u)
            data.outputValue(AccelMotionPath.dist).setFloat(dist)
        else:
            return OpenMaya.kUnknownParameter

        data.setClean(plug)  # Tell Maya that we have updated some attributes


# Creator for the accelMotionPath node (above)
def accelMotionPathCreator():
    return OpenMayaMPx.asMPxPtr(AccelMotionPath())


# Initializes the accelMotionPath node
# Attributes are added to the Channel Box in the order created; so to keep things nice for the user, we initialize
# the attributes in a logical order.
def initialize():
    # Initializes a numeric attribute creator
    nAttr = OpenMaya.MFnNumericAttribute()

    # Create time attribute
    AccelMotionPath.time = nAttr.create("time", "time", OpenMaya.MFnNumericData.kFloat, 1.0)
    nAttr.setWritable(True)
    nAttr.setReadable(False)
    nAttr.setStorable(False)
    nAttr.setKeyable(False)
    nAttr.setChannelBox(False)
    AccelMotionPath.addAttribute(AccelMotionPath.time)

    # Create timeInit attribute
    AccelMotionPath.timeInit = nAttr.create("startTime", "timeInit", OpenMaya.MFnNumericData.kFloat, 1.0)
    nAttr.setWritable(True)
    nAttr.setReadable(True)
    nAttr.setStorable(True)
    nAttr.setKeyable(False)
    nAttr.setChannelBox(True)
    nAttr.setMin(0.0)
    AccelMotionPath.addAttribute(AccelMotionPath.timeInit)

    # Create timeLast attribute
    AccelMotionPath.timeLast = nAttr.create("lastTime", "timeLast", OpenMaya.MFnNumericData.kFloat, 1.0)
    nAttr.setWritable(True)
    nAttr.setReadable(False)
    nAttr.setStorable(False)
    nAttr.setKeyable(False)
    nAttr.setChannelBox(False)
    AccelMotionPath.addAttribute(AccelMotionPath.timeLast)

    # Create posInit attribute
    AccelMotionPath.posInit = nAttr.create("startPosition", "posInit", OpenMaya.MFnNumericData.kFloat, 0.0)
    nAttr.setWritable(True)
    nAttr.setReadable(True)
    nAttr.setStorable(True)
    nAttr.setKeyable(False)
    nAttr.setChannelBox(True)
    nAttr.setMin(0.0)
    AccelMotionPath.addAttribute(AccelMotionPath.posInit)

    # Create velInit attribute
    AccelMotionPath.velInit = nAttr.create("startVelocity", "velInit", OpenMaya.MFnNumericData.kFloat, 0.0)
    nAttr.setWritable(True)
    nAttr.setReadable(True)
    nAttr.setStorable(True)
    nAttr.setKeyable(False)
    nAttr.setChannelBox(True)
    AccelMotionPath.addAttribute(AccelMotionPath.velInit)

    # Create vel attribute
    AccelMotionPath.vel = nAttr.create("velocity", "vel", OpenMaya.MFnNumericData.kFloat, 0.0)
    nAttr.setWritable(True)
    nAttr.setReadable(True)
    nAttr.setStorable(False)
    nAttr.setKeyable(False)  # Required to be false for whatever reason. It will still be keyable though. (I hate Maya.)
    nAttr.setChannelBox(True)
    AccelMotionPath.addAttribute(AccelMotionPath.vel)

    # Create killVel attribute
    AccelMotionPath.killVel = nAttr.create("killVelocity", "killVel", OpenMaya.MFnNumericData.kFloat, 0.0)
    nAttr.setWritable(True)
    nAttr.setReadable(True)
    nAttr.setStorable(True)
    nAttr.setKeyable(False)
    nAttr.setChannelBox(True)
    AccelMotionPath.addAttribute(AccelMotionPath.killVel)

    # Create accel attribute
    AccelMotionPath.accel = nAttr.create("acceleration", "accel", OpenMaya.MFnNumericData.kFloat, 0.0)
    nAttr.setWritable(True)
    nAttr.setReadable(True)
    nAttr.setStorable(True)
    nAttr.setKeyable(False)
    nAttr.setChannelBox(True)
    AccelMotionPath.addAttribute(AccelMotionPath.accel)

    # Create u attribute
    AccelMotionPath.u = nAttr.create("uValue", "u", OpenMaya.MFnNumericData.kFloat, 0.0)
    nAttr.setWritable(False)
    nAttr.setReadable(True)
    nAttr.setStorable(False)
    nAttr.setKeyable(False)
    nAttr.setChannelBox(True)
    AccelMotionPath.addAttribute(AccelMotionPath.u)

    # Create uLast attribute
    AccelMotionPath.uLast = nAttr.create("lastUValue", "uLast", OpenMaya.MFnNumericData.kFloat, 0.0)
    nAttr.setWritable(True)
    nAttr.setReadable(False)
    nAttr.setStorable(False)
    nAttr.setKeyable(False)
    nAttr.setChannelBox(False)
    AccelMotionPath.addAttribute(AccelMotionPath.uLast)

    # Create arcLen attribute
    AccelMotionPath.arcLen = nAttr.create("arcLength", "arcLen", OpenMaya.MFnNumericData.kFloat, 0.0)
    nAttr.setWritable(True)
    nAttr.setReadable(True)
    nAttr.setStorable(False)
    nAttr.setKeyable(False)
    nAttr.setChannelBox(False)
    AccelMotionPath.addAttribute(AccelMotionPath.arcLen)

    # Create dist attribute
    AccelMotionPath.dist = nAttr.create("distance", "dist", OpenMaya.MFnNumericData.kFloat, 0.0)
    nAttr.setWritable(True)
    nAttr.setReadable(True)
    nAttr.setStorable(False)
    nAttr.setKeyable(False)
    nAttr.setChannelBox(True)
    AccelMotionPath.addAttribute(AccelMotionPath.dist)

    # Tell Maya which attributes should affect the position of the object along the curve (u-value)
    AccelMotionPath.attributeAffects(AccelMotionPath.timeInit, AccelMotionPath.u)
    AccelMotionPath.attributeAffects(AccelMotionPath.time, AccelMotionPath.u)
    AccelMotionPath.attributeAffects(AccelMotionPath.posInit, AccelMotionPath.u)
    AccelMotionPath.attributeAffects(AccelMotionPath.velInit, AccelMotionPath.u)
    AccelMotionPath.attributeAffects(AccelMotionPath.killVel, AccelMotionPath.u)
    AccelMotionPath.attributeAffects(AccelMotionPath.arcLen, AccelMotionPath.u)

    # Tell Maya which attributes should be updated when the u-value changes
    AccelMotionPath.attributeAffects(AccelMotionPath.u, AccelMotionPath.timeLast)
    AccelMotionPath.attributeAffects(AccelMotionPath.u, AccelMotionPath.vel)
    AccelMotionPath.attributeAffects(AccelMotionPath.u, AccelMotionPath.uLast)
    AccelMotionPath.attributeAffects(AccelMotionPath.u, AccelMotionPath.dist)


def initializePlugin(obj):
    # Initialize plugin object
    plugin = OpenMayaMPx.MFnPlugin(obj, "Jake Cheek", "1.0", "Any")

    # Register the accelMotionPath node with Maya
    try:
        plugin.registerNode("accelMotionPath", AccelMotionPath.kPluginNodeId, accelMotionPathCreator, initialize)
    except:
        raise RuntimeError("Failed to register accelMotionPath node")

    # Register the command to create an accelMotionPath with Maya
    try:
        plugin.registerCommand("createAccelMotionPath", createAccelMotionPathCreator)
    except:
        raise RuntimeError("Failed to register createAccelMotionPath command")

    # Create a menu that the user can create accelMotionPaths from
    menu = cmds.menu("accelMotionPathMenu", parent="MayaWindow", label="Accel Motion Path", tearOff=True)
    cmds.menuItem("createAccelMotionPathMenuItem", parent=menu, label="Attach to Accel Motion Path",
                  command="cmds.createAccelMotionPath()")


def uninitializePlugin(obj):
    # Get the plugin object
    plugin = OpenMayaMPx.MFnPlugin(obj)

    # Deregister the accelMotionPath node
    try:
        plugin.deregisterNode(AccelMotionPath.kPluginNodeId)
    except:
        raise RuntimeError("Failed to deregister accelMotionPath node")

    # Deregister the command to create an accelMotionPath
    try:
        plugin.deregisterCommand("createAccelMotionPath")
    except:
        raise RuntimeError("Failed to deregister createAccelMotionPath command")

    # Remove the custom menu
    if cmds.menu("accelMotionPathMenu", q=True, exists=True):
        cmds.deleteUI("accelMotionPathMenu")


# Since Maya loves to make things difficult, we have to use this to convert the current playback rate to an integer
def getFPS():
    timeUnit = cmds.currentUnit(query=True, time=True)

    if timeUnit == "game":
        return 15
    elif timeUnit == "film":
        return 24
    elif timeUnit == "pal":
        return 25
    elif timeUnit == "ntsc":
        return 30
    elif timeUnit == "show":
        return 48
    elif timeUnit == "palf":
        return 50
    elif timeUnit == "ntscf":
        return 60
    elif timeUnit == "2fps":
        return 2
    elif timeUnit == "3fps":
        return 3
    elif timeUnit == "4fps":
        return 4
    elif timeUnit == "5fps":
        return 5
    elif timeUnit == "6fps":
        return 6
    elif timeUnit == "8fps":
        return 8
    elif timeUnit == "10fps":
        return 10
    elif timeUnit == "12fps":
        return 12
    elif timeUnit == "16fps":
        return 16
    elif timeUnit == "20fps":
        return 20
    elif timeUnit == "23.976fps":
        return 24.0 * 1000.0 / 1001.0
    elif timeUnit == "29.97fps":
        return 30.0 * 1000.0 / 1001.0
    elif timeUnit == "29.97df":
        return 30.0 * 1000.0 / 1001.0
    elif timeUnit == "40fps":
        return 40
    elif timeUnit == "47.952fps":
        return 48.0 * 1000.0 / 1001.0
    elif timeUnit == "59.94fps":
        return 60.0 * 1000.0 / 1001.0
    elif timeUnit == "75fps":
        return 75
    elif timeUnit == "80fps":
        return 80
    elif timeUnit == "100fps":
        return 100
    elif timeUnit == "120fps":
        return 120
    elif timeUnit == "125fps":
        return 125
    elif timeUnit == "150fps":
        return 150
    elif timeUnit == "200fps":
        return 200
    elif timeUnit == "240fps":
        return 240
    elif timeUnit == "250fps":
        return 250
    elif timeUnit == "300fps":
        return 300
    elif timeUnit == "375fps":
        return 375
    elif timeUnit == "400fps":
        return 400
    elif timeUnit == "500fps":
        return 500
    elif timeUnit == "600fps":
        return 600
    elif timeUnit == "750fps":
        return 750
    elif timeUnit == "1200fps":
        return 1200
    elif timeUnit == "1500fps":
        return 1500
    elif timeUnit == "2000fps":
        return 2000
    elif timeUnit == "3000fps":
        return 3000
    elif timeUnit == "6000fps":
        return 6000
    elif timeUnit == "44100fps":
        return 41000
    elif timeUnit == "48000fps":
        return 48000

    return -1
