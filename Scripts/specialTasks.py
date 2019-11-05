from qpaceExperiment import Camera

def task_takePicture():
    print("TASK")
    try:
        cam = Camera()
        cam.set(fps=90, w=640,h=480,cfx=(128,128), br=80,sh=75)
        cam.capture(filename='specialTasks')
    except Exception as e:
        print(e)
    finally:
        print("TASK DONE")
