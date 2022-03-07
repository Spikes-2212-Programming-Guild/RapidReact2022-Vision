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
cs = None


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


def autonomous_camera_server_thread(defaultPort, name):
    global cs
    global capturing
    global cargo_frame
    nt = NetworkTables.getTable("Camera ports")
    last_cam_id = cam_id = int(nt.getNumber("current " + name, defaultValue=defaultPort))
    cam = cv2.VideoCapture(cam_id)
    cam_table = NetworkTables.getTable("CameraPublisher/" + name)
    cam_table.getEntry("streams")

    if not cs:
        cs = CameraServer()
        cs.enableLogging()

    width = 640
    height = 480

    cam_output = cs.putVideo(name, width, height)

    try:
        while capturing:
            cam_id = int(nt.getNumber("current " + name, defaultValue=defaultPort))
            if cam_id != last_cam_id:
                cam.release()
                cam = cv2.VideoCapture(cam_id)

            last_cam_id = cam_id
            success, cargo_frame = cam.read()

            if not success or cargo_frame or cargo_frame is None:
                continue

            cam_output.putFrame(cargo_frame)
    finally:
        cam.release()
        print(name + " thread done!")


def camera_server_thread(defaultPort, name):
    global cs
    global capturing
    nt = NetworkTables.getTable("Camera ports")
    last_cam_id = cam_id = int(nt.getNumber("current " + name, defaultValue=defaultPort))
    cam = cv2.VideoCapture(cam_id)
    cam_table = NetworkTables.getTable("CameraPublisher/" + name)
    cam_table.getEntry("streams")

    if not cs:
        cs = CameraServer()
        cs.enableLogging()

    width = 640
    height = 480

    cam_output = cs.putVideo(name, width, height)

    try:
        while capturing:
            cam_id = int(nt.getNumber("current " + name, defaultValue=defaultPort))
            if cam_id != last_cam_id:
                cam.release()
                cam = cv2.VideoCapture(cam_id)

            last_cam_id = cam_id
            success, frame = cam.read()

            if not success:
                continue

            cam_output.putFrame(frame)
    finally:
        cam.release()
        print(name + " thread done!")


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
    intake_camera_server_thread = Thread(target=autonomous_camera_server_thread, args=(0, "cargoCam"))
    back_camera_server_thread = Thread(target=camera_server_thread, args=(2, "backCam"))
    intake_camera_server_thread.start()
    back_camera_server_thread.start()
    time.sleep(1)
    networkTableImageProcessing = NetworkTables.getTable("Image Processing")
    try:
        main()

    finally:
        end()
        print("Job's done!")
