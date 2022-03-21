import time
from datetime import datetime

from networktables import NetworkTables
from grip import RedCargo
from grip import BlueCargo
import cv2
from threading import Thread, Lock
from cscore import CameraServer

cargo_frame = None
pipeline = None

contour_count = 1

lock = Lock()


def start_pipeline(networkTableImageProcessing, cs):
    """
    uses the GRIP pipline to process the current frame
    :return:
    """
    global cargo_frame
    global pipeline
    contour_count = 1

    cam_table = NetworkTables.getTable("CameraPublisher/GRIP")
    cam_table.getEntry("streams")

    while cargo_frame is None or not NetworkTables.isConnected():  # checks if something is wrong
        print(f"NT connection: {NetworkTables.isConnected()}")
        print(f"Cargo frame is none? {cargo_frame is None}")
    [networkTableImageProcessing.delete(s) for s in networkTableImageProcessing.getKeys()]

    grip_output = cs.putVideo("GRIP", 300, 230)

    while True:
        update_pipeline()
        with lock:
            pipeline.process(cargo_frame)
        contours = sorted(pipeline.filter_contours_output, key=cv2.contourArea, reverse=True)
        grip_output.putFrame(pipeline.mask_output)

        contour_count = max(contour_count, len(contours))
        put_contours_in_nt(contours, networkTableImageProcessing)


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


def autonomous_camera_server_thread(cs, defaultPort, name):
    global cargo_frame
    writer = cv2.VideoWriter(f"images/{datetime.now().strftime('%H:%M:%S')}.avi",cv2.VideoWriter_fourcc('M','J','P','G'), 20, (320, 240))
    nt = NetworkTables.getTable("Camera ports")
    last_cam_id = cam_id = int(nt.getNumber("current " + name, defaultValue=defaultPort))
    cam = cv2.VideoCapture(cam_id)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    cam_table = NetworkTables.getTable("CameraPublisher/" + name)
    cam_table.getEntry("streams")

    width = 320
    height = 240

    cam_output = cs.putVideo(name, width, height)

    first_time = time.gmtime()
    current_time = time.gmtime()

    done_writing = False

    try:
        while True:
            cam_id = int(nt.getNumber("current " + name, defaultValue=defaultPort))
            if cam_id != last_cam_id:
                cam.release()
                cam = cv2.VideoCapture(cam_id)

            last_cam_id = cam_id
            with lock:
                success, cargo_frame = cam.read()

            if not success or cargo_frame is None:
                print(f"Could not read from camera in thread {name}")
                continue

            if 15 >= current_time.tm_sec - first_time.tm_sec > 0 and not done_writing:
                current_time = time.gmtime()
                print(current_time.tm_sec - first_time.tm_sec)
                writer.write(cargo_frame)
            elif current_time.tm_sec - first_time.tm_sec < 0:
                done_writing = True

            cam_output.putFrame(cargo_frame)

    finally:
        cam.release()
        print(name + " thread done!")


def camera_server_thread(cs, defaultPort, name):
    nt = NetworkTables.getTable("Camera ports")
    last_cam_id = cam_id = int(nt.getNumber("current " + name, defaultValue=defaultPort))
    cam = cv2.VideoCapture(cam_id)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    cam_table = NetworkTables.getTable("CameraPublisher/" + name)
    cam_table.getEntry("streams")

    width = 320
    height = 240

    cam_output = cs.putVideo(name, width, height)

    try:
        while True:
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


def put_contours_in_nt(contours, networkTableImageProcessing):
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
    networkTableImageProcessing = NetworkTables.getTable("Image Processing")
    [networkTableImageProcessing.delete(s) for s in networkTableImageProcessing.getKeys()]

    for sub in networkTableImageProcessing.getSubTables():
        sub = networkTableImageProcessing.getSubTable(sub)
        [sub.delete(k) for k in sub.getKeys()]


def main():
    cs = CameraServer()
    cs.enableLogging()

    print("Starting")
    NetworkTables.initialize("10.22.12.2")  # The ip of the roboRIO
    intake_camera_server_thread = Thread(target=autonomous_camera_server_thread, args=(cs, 0, "cargoCam"))
    intake_camera_server_thread.start()
    time.sleep(1)
    networkTableImageProcessing = NetworkTables.getTable("Image Processing")

    try:
        start_pipeline(networkTableImageProcessing, cs)

    finally:
        end()
        print("Job's done!")


if __name__ == "__main__":
    main()
