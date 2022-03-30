import os
import time
from datetime import datetime
from threading import Thread, Lock

import cv2
from cscore import CameraServer
from networktables import NetworkTables

from grip import BlueCargo
from grip import RedCargo

cargo_frame = None
pipeline = None

contour_count = 1

SETPOINT = -10

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
    nt = NetworkTables.getTable("Camera ports")
    last_cam_id = cam_id = int(nt.getNumber("current " + name, defaultValue=defaultPort))
    cam = cv2.VideoCapture(cam_id)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    cam_table = NetworkTables.getTable("CameraPublisher/" + name)
    cam_table.getEntry("streams")

    # is_in_auto_table = NetworkTables.getTable("robot namespace")

    width = 320
    height = 240

    cam_output = cs.putVideo(name, width, height)

    match_type_name = "qual"
    # station = 0
    match_number = 0
    try:
        info_table = NetworkTables.getTable("FMSInfo")
        match_type = info_table.getNumber("MatchType", 0)
        match_number = info_table.getNumber("MatchNumber", 0)
        # station = info_table.getNumber("StationNumber", 0)

        if match_type == 1:
            match_type_name = "pr"
        elif match_type == 2:
            match_type_name = "qual"
        elif match_type == 3:
            match_type_name = "play"
    except:
        pass

    last_frame_time = time.time()
    seconds_per_frame = 2
    index = 0

    # with open("/home/pi/Grip/images/DCMP/names.txt", "a") as f:
    #     f.write(str(match_type_name) + "STATION:" + str(station) + "\n")

    # if match_type != 0:
    os.chdir(f"/home/pi/Grip/images/DCMP")
    new_dir = f"{match_type_name} - {match_number} {datetime.now().strftime('%H:%M:%S')}/"
    os.mkdir(new_dir)
    os.chdir(new_dir)

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

            # if match_type != 0:
            try:
                if time.time() > last_frame_time + seconds_per_frame:
                    cv2.imwrite(f"{index}.jpg", cargo_frame)
                    last_frame_time = time.time()
                    index += 1
            except:
                pass

            cam_output.putFrame(cargo_frame)

    finally:
        cam.release()
        print(name + " thread done!")


def camera_server_thread(cs, defaultPort, name):
    nt = NetworkTables.getTable("Camera ports")
    last_cam_id = cam_id = int(nt.getNumber("cu rrent " + name, defaultValue=defaultPort))
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
    for i, c in enumerate(contours[0:contour_count]):
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
        nt.putNumber("x", SETPOINT)


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
