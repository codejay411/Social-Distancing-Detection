from flask import Flask, render_template, Response, request, redirect
from werkzeug.utils import secure_filename
from werkzeug.datastructures import  FileStorage
from detect_person import social_distancing_config as config
from detect_person.detection import detect_people
from scipy.spatial import distance as dist
import numpy as np
from flask import flash
import argparse
import imutils
import time
import cv2 
import os



# load the COCO class labels our YOLO model was trained on
labelsPath = os.path.sep.join([config.MODEL_PATH, "coco.names"])
LABELS = open(labelsPath).read().strip().split("\n")

# derive the paths to the YOLO weights and model configuration
weightsPath = os.path.sep.join([config.MODEL_PATH, "yolov3.weights"])
configPath = os.path.sep.join([config.MODEL_PATH, "yolov3.cfg"])

# load our YOLO object detector trained on COCO dataset (80 classes)
print("[INFO] loading YOLO from disk...")
net = cv2.dnn.readNetFromDarknet(configPath, weightsPath)

# check if we are going to use GPU
if config.USE_GPU:
	# set CUDA as the preferable backend and target
	print("[INFO] setting preferable backend and target to CUDA...")
	net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
	net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)

# determine only the *output* layer names that we need from YOLO
ln = net.getLayerNames()
ln = [ln[i - 1] for i in net.getUnconnectedOutLayers()]


app=Flask(__name__)

"""Video streaming generator function."""
def generate_frames(display):
    
	if display:
		vs = cv2.VideoCapture(os.path.join("output video", display))
	else:
		vs = cv2.VideoCapture(display)
		
	writer = None

    # loop over the frames from the video stream
	while True:
    	# read the next frame from the file
		(grabbed, frame) = vs.read()

    	# if the frame was not grabbed, then we have reached the end
    	# of the stream
		if not grabbed:
			break

    	# resize the frame and then detect people (and only people) in it
		frame = imutils.resize(frame, width=700)
		results = detect_people(frame, net, ln,
    		personIdx=LABELS.index("person"))

    	# initialize the set of indexes that violate the minimum social
    	# distance
		violate = set()

    	# ensure there are *at least* two people detections (required in
    	# order to compute our pairwise distance maps)
		if len(results) >= 2:
    		# extract all centroids from the results and compute the
    		# Euclidean distances between all pairs of the centroids
			centroids = np.array([r[2] for r in results])
			D = dist.cdist(centroids, centroids, metric="euclidean")

    		# loop over the upper triangular of the distance matrix
			for i in range(0, D.shape[0]):
				for j in range(i + 1, D.shape[1]):
    				# check to see if the distance between any two
    				# centroid pairs is less than the configured number
    				# of pixels
					if D[i, j] < config.MIN_DISTANCE:
    					# update our violation set with the indexes of
    					# the centroid pairs
						violate.add(i)
						violate.add(j)

    	# loop over the results
		for (i, (prob, bbox, centroid)) in enumerate(results):
    		# extract the bounding box and centroid coordinates, then
    		# initialize the color of the annotation
			(startX, startY, endX, endY) = bbox
			(cX, cY) = centroid
			color = (0, 255, 0)

    		# if the index pair exists within the violation set, then
    		# update the color
			if i in violate:
				color = (0, 0, 255)

    		# draw (1) a bounding box around the person and (2) the
    		# centroid coordinates of the person,
			cv2.rectangle(frame, (startX, startY), (endX, endY), color, 2)
			cv2.circle(frame, (cX, cY), 5, color, 1)

    	# draw the total number of social distancing violations on the
    	# output frame
		text = "Social Distancing Violations: {}".format(len(violate))
		cv2.putText(frame, text, (10, frame.shape[0] - 25),
    		cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 0, 255), 3)

    	# check to see if the output frame should be displayed to our
    	# screen
		if 1 > 0:
    		# show the output frame
    		# cv2.imshow("Frame", frame)
			frame = cv2.imencode('.jpg', frame)[1].tobytes()

			yield (b'--frame\r\n'b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')




@app.route('/')
def index():
    return render_template('index.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/about')
def about():
    return render_template('about-us.html')

@app.route('/detection', methods = ['GET', 'POST'])
def detection():
	if request.method == "POST":
		if 'upload' not in request.files:
			# flash('No file part')
			print("no file part")
			return redirect("/")
		file = request.files['upload']
		if file.filename == '':
			flash('No image selected for uploading')
			return redirect(request.url)
		else:
			# base_path = os.path.abspath(os.path.dirname(__file__))
			# print(base_path)
			# upload_path = os.path.join(base_path, "video")
			# print(upload_path)
			# f.save(os.path.join(upload_path, secure_filename(f.filename)))
			# filename = secure_filename(file.filename)
			filename = "output.mp4"
			file.save(os.path.join("output video", filename))
			# print('upload_video filename: ' + filename)
			print("successful")
			# flash('Video successfully uploaded and displayed below')
			return render_template('detection.html', filename=filename)
	return render_template('detection.html')

@app.route('/detectioncam')
def detectioncam():
	# display = 0
	return render_template('detectioncam.html')

@app.route('/video/<filename>')
def video(filename):
	print('display_video filename: ' + filename)
	display = filename
	return Response(generate_frames(display),mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/videocam')
def videocam():
	display = 0
	return Response(generate_frames(display),mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__=="__main__":
    app.run(debug=True)