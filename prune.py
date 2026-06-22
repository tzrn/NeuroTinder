from PIL import Image
import os
import numpy as np
import threading

imgdir = "static/img/pfp/"
files = os.listdir(imgdir)


imgs = {}
threads = []
lock = threading.Lock()


def addimg(filename):
    img = np.array(Image.open(imgdir + filename).resize((20, 20)).convert("L"))
    with lock:
        imgs[filename] = img


print("loading images...")
for i in files:
    t = threading.Thread(target=addimg, args=(i,))
    threads.append(t)
    t.start()

for t in threads:
    t.join()

print("comparing...")
dupes = set()
imgnames = list(imgs)
for i in range(len(imgnames)):
    for j in range(i + 1, len(imgnames)):
        diff = np.abs(imgs[imgnames[i]] - imgs[imgnames[j]]).sum()
        if diff < 15_000:
            dupes.add(imgnames[j])
            print(imgnames[i], imgnames[j])

for i in dupes:
    os.remove(imgdir + i)
