import time

from networktables import NetworkTables
from grip import RedCargo
from grip import BlueCargo
import cv2
from threading import Thread
from cscore import CameraServer

frame = None
capturing = True
pipeline = None
contour_count = 1


def main():
    """
    uses the GRIP pipline to process the current frame
    :return:
    """
    global contour_count

    while frame is None or not NetworkTables.isConnected():  # checks if something is wrong
        print(f"NT connection: {NetworkTables.isConnected()}")
    [networkTableImageProcessing.delete(s) for s in networkTableImageProcessing.getKeys()]

    while True:
        # cargoCamTime, cargoCamImg = cargoCamSink.grabFrame(np.array(0))
        update_pipeline()
        print("Processing...")
        pipeline.process(frame)
        contours = sorted(pipeline.filter_contours_output, key=cv2.contourArea, reverse=True)
        contour_count = max(contour_count, len(contours))
        put_contours_in_nt(contours)
        # cargoCamOutput.putFrame(cargoCamImg)


def update_pipeline():
    """
    changes the pipline according to the team's correct color in the match
    """
    global pipeline
    if not NetworkTables.getTable("FMSInfo").getBoolean("IsRedAlliance", True):
        pipeline = BlueCargo()
    else:
        pipeline = RedCargo()
    print(f"PIPE {pipeline}")


def update_image():
    """
    grabs the frame from the right camera that needs to be processed.
    """
    global frame
    global capturing
    nt = NetworkTables.getTable("Image Processing")
    last_id = cam_id = int(nt.getNumber("currentCamera", defaultValue=0))
    cam = cv2.VideoCapture(cam_id)

    # cargoCamTable = NetworkTables.getTable("CameraPublisher/cargoCam")
    # cargoCamEntry = cargoCamTable.getEntry("streams")

    # cs = CameraServer()
    # cs.enableLogging()

    # width = 300
    # height = 230

    # cargoCam = cs.startAutomaticCapture(dev=0)
    # cargoCam.setResolution(width, height)

    # cargoCamSink = cs.getVideo(camera=cargoCam)

    # currentPort = 1181

    # cargoCamOutput = cs.putVideo("CargoCam", width, height)
    # cargoCamEntry.setStringArray([f"mjpeg:http://10.22.12.51:{currentPort}/?action=stream"])
    # currentPort += 1

    cargoCamTable = NetworkTables.getTable("CameraPublisher/cargoCam")
    cargoCamEntry = cargoCamTable.getEntry("streams")

    cs = CameraServer()
    cs.enableLogging()

    width = 1280
    height = 720

    cargoCamSink = cs.getVideo(camera=cam)
    cargoCamOutput = cs.putVideo("Cargo Camera", width, height)

    try:
        while capturing:
            cam_id = int(nt.getNumber("currentCamera", defaultValue=0))
            if last_id != cam_id:
                cam.release()
                cam = cv2.VideoCapture(cam_id)
            last_id = cam_id
            success, frame = cam.read()

            cargoCamOutput.putFrame(frame)

    finally:
        cam.release()
        print("Thread's done!")


def put_contours_in_nt(contours):
    """
    puts the data from the bounding rectangle of the contours in the network-tables.
    :param contours: the contours to get the data from
    """
    for i, c in enumerate(contours):
        nt = networkTableImageProcessing.getSubTable(f"contour {i}")
        nt.putNumber(f'area', cv2.contourArea(c))

        x, y, w, h = cv2.boundingRect(c)

        nt.putNumber(f'width', w)

        nt.putNumber(f'height', h)

        nt.putNumber(f'x', x - 300 / 2)

        nt.putNumber(f'y', y)

        nt.putBoolean(f'isUpdated', True)

    for i in range(len(contours), contour_count):
        nt = networkTableImageProcessing.getSubTable(f"contour {i}")
        nt.putBoolean(f'isUpdated', False)
        nt.putNumber("x", 0)


def end():
    """
    the end of the program - closes everything and deletes everything from the nnetwork-tables
    :return:
    """
    global capturing
    capturing = False
    [networkTableImageProcessing.delete(s) for s in networkTableImageProcessing.getKeys()]

    for sub in networkTableImageProcessing.getSubTables():
        sub = networkTableImageProcessing.getSubTable(sub)
        [sub.delete(k) for k in sub.getKeys()]


if __name__ == "__main__":
    print("Starting")
    NetworkTables.initialize("10.22.12.2")  # The ip of the roboRIO
    t = Thread(target=update_image)
    t.start()
    time.sleep(1)
    networkTableImageProcessing = NetworkTables.getTable("Image Processing")
    try:
        main()

    finally:
        end()
        print("Job's done!")
