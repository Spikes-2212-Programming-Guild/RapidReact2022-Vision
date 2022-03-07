import time

from networktables import NetworkTables
from grip import RedCargo
from grip import BlueCargo
import cv2
from threading import Thread
from cscore import CameraServer

cargo_frame = None
capturing = True
pipeline = None
contour_count = 1


def main():
    """
    uses the GRIP pipline to process the current frame
    :return:
    """
    global contour_count

    while cargo_frame is None or not NetworkTables.isConnected():  # checks if something is wrong
        print(f"NT connection: {NetworkTables.isConnected()}")
    [networkTableImageProcessing.delete(s) for s in networkTableImageProcessing.getKeys()]

    while True:
        update_pipeline()
        print("Processing...")
        pipeline.process(cargo_frame)
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
    global cargo_frame
    global capturing
    nt = NetworkTables.getTable("Image Processing")
    cargo_cam_last_id = cargo_cam_id = int(nt.getNumber("current Cargo Camera", defaultValue=0))
    back_cam_last_id = back_cam_id = int(nt.getNumber("current Back Camera", defaultValue=2))
    cargo_cam = cv2.VideoCapture(cargo_cam_id)
    back_cam = cv2.VideoCapture(back_cam_id)

    cargo_cam_table = NetworkTables.getTable("CameraPublisher/cargoCam")
    back_cam_table = NetworkTables.getTable("CameraPublisher/backCamera")

    cargo_cam_table.getEntry("streams")
    back_cam_table.getEntry("streams")

    cs = CameraServer()
    cs.enableLogging()

    width = 1280
    height = 720

    cargo_cam_output = cs.putVideo("Cargo Camera", width, height)
    back_cam_output = cs.putVideo("Back Camera", width, height)

    try:
        while capturing:
            cargo_cam_id = int(nt.getNumber("current Cargo Camera", defaultValue=0))
            back_cam_id = int(nt.getNumber("current Back Camera", defaultValue=2))
            if cargo_cam_last_id != cargo_cam_id:
                cargo_cam.release()
                cargo_cam = cv2.VideoCapture(cargo_cam_id)

            if back_cam_last_id != back_cam_id:
                back_cam.release()
                back_cam = cv2.VideoCapture(back_cam_id)

            cargo_cam_last_id = cargo_cam_id
            back_cam_last_id = back_cam_id
            cargo_success, cargo_frame = cargo_cam.read()
            back_success, back_frame = back_cam.read()

            cargo_cam_output.putFrame(cargo_frame)
            back_cam_output.putFrame(back_frame)

    finally:
        cargo_cam.release()
        back_cam.release()
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
