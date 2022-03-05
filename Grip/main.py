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
        update_pipeline()
        print("Processing...")
        pipeline.process(frame)
        contours = sorted(pipeline.filter_contours_output, key=cv2.contourArea, reverse=True)
        contour_count = max(contour_count, len(contours))
        put_contours_in_nt(contours)


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
    cargoCam_last_id = cargoCam_id = int(nt.getNumber("currentCamera", defaultValue=0))
    backCam_last_id2 = backCam_id = int(nt.getNumber("currentCamera2", defaultValue=2))
    cargoCam = cv2.VideoCapture(cargoCam_id)
    backCam = cv2.VideoCapture(backCam_id)

    cargoCamTable = NetworkTables.getTable("CameraPublisher/cargoCam")
    backCamTable = NetworkTables.getTable("CameraPublisher/backCamera")

    cargoCamTable.getEntry("streams")
    backCamTable.getEntry("streams")

    cs = CameraServer()
    cs.enableLogging()

    width = 1280
    height = 720

    cargoCamOutput = cs.putVideo("Cargo Camera", width, height)
    backCamOutput = cs.putVideo("Back Camera", width, height)

    try:
        while capturing:
            cargoCam_id = int(nt.getNumber("currentCamera", defaultValue=0))
            backCam_id = int(nt.getNumber("backCamera", defaultValue=2))
            if cargoCam_last_id != cargoCam_id:
                cargoCam.release()
                cargoCam = cv2.VideoCapture(cargoCam_id)

            if backCam_last_id2 != backCam_id:
                backCam.release()
                backCam = cv2.VideoCapture(backCam_id)

            cargoCam_last_id = cargoCam_id
            backCam_last_id2 = backCam_id
            success, frame = cargoCam.read()
            success2, frame2 = backCam.read()

            cargoCamOutput.putFrame(frame)
            backCamOutput.putFrame(frame2)

    finally:
        cargoCam.release()
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
