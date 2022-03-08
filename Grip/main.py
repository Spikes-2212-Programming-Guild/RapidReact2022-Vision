import time
from multiprocessing import Process
from threading import Thread

import redis
from cscore import CameraServer
from cv2 import cv2
from networktables import NetworkTables

from grip import BlueCargo
from grip import RedCargo
from redis_commu import *

cargo_frame = None
updating = False
capturing = True
pipeline = None
contour_count = 1

cs = CameraServer()
red = redis.Redis(host='localhost', port=6379, db=0)

width = 1280
height = 720


def main():
    """
    uses the GRIP pipline to process the current frame
    :return:
    """
    global contour_count

    while cargo_frame is None or not NetworkTables.isConnected():  # checks if something is wrong
        print(f"NT connection: {NetworkTables.isConnected()}")
        print(f"CARGO FRAME: {cargo_frame}")
        time.sleep(1)
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


def update_image():
    """
    grabs the frame from the right camera that needs to be processed.
    """
    global cargo_frame
    global capturing

    nt = NetworkTables.getTable("Image Processing")
    cargo_cam_last_id = cargo_cam_id = int(nt.getNumber("current Cargo Camera", defaultValue=0))
    back_cam_last_id = back_cam_id = int(nt.getNumber("current Back Camera", defaultValue=2))
    print("opening cameras")
    cargo_cam = cv2.VideoCapture(cargo_cam_id)
    print("opened cargo cam")
    back_cam = cv2.VideoCapture(back_cam_id)
    print("opened back cam")

    back_cam_table = NetworkTables.getTable("CameraPublisher/Back Camera")

    print("done stuff")

    back_cam_table.getEntry("streams")

    cargo_cam_proc = Process(target=cargo_cam_handler)
    cargo_cam_proc.start()
    # cargo_cam_proc.join()

    print("set tables streams")

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
            print("cargo frame:", cargo_frame)
            back_success, back_frame = back_cam.read()

            to_redis(red, cargo_frame, 'cargo cam')
            to_redis(red, back_frame, 'back cam')

    finally:
        cargo_cam.release()
        back_cam.release()
        print("Thread's done!")


def cargo_cam_handler():
    time.sleep(5)
    cargo_cam_table = NetworkTables.getTable("CameraPublisher/Cargo Camera")
    cargo_cam_table.getEntry("streams")

    print("started cargo cam thread")
    cargo_cam_output = cs.putVideo("Cargo Camera", width, height)
    print("configured cargo cam output")
    while capturing:
        print("mnn")
        cargo_cam_output.putFrame(from_redis(red, 'cargo cam'))


def back_cam_handler():
    print("started back cam thread")
    back_cam_output = cs.putVideo("Back Camera", width, height)
    print("configured back cam output")
    while capturing:
        back_cam_output.putFrame(from_redis(red, 'back cam'))


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
    print("NT Initialized")
    t = Thread(target=update_image)
    t.start()

    time.sleep(1)
    networkTableImageProcessing = NetworkTables.getTable("Image Processing")
    try:
        main()

    finally:
        end()
        print("Job's done!")
