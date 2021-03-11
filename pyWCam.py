# C:\python
# By dascondor

import argparse
import socket
import textwrap
from flask import Flask, flash, redirect, render_template, request, session, abort, Response
from camera import VideoCamera
import cv2

my_parser = argparse.ArgumentParser(
    prog='pyWCam',
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description=textwrap.dedent('''\
            ________________________        pyWCam 0.1.1       ________________________
            
            Use:
            --------------------------------
            By default, will publish a webpage for local viewing of a webcam
            @ 127.0.0.1:8080; Port is configurable.
            

            Parameters:
            ---------------------------------------------------------------------------
            -host          --hosted           By default this is False          
                                              I.E. publish the webpage

            -po            --port             By default set to 8080

            -iid           --HTMLIndexID      By default set to basic option 1

                                                *IndexID 1:
                                                w1278 x h720
                                                no options; simple

                                                *IndexID 2:
                                                2 modular windows, 
                                                w800 x h600 
                                                with the first being live video
                                                second to view captured image                

            By dascondor & Alfren
            '''),
    epilog="""---------------------------Alls well what ends well------------------------""")
my_parser.version = '1.01'
my_parser.add_argument('-host', '--hosted', action='store_true', default=False)
my_parser.add_argument('-po', '--port', type=int, default='8080')
my_parser.add_argument('-iid', '--HTMLIndexID', default=1, type=int)


app = Flask(__name__)

video_stream = VideoCamera()

@app.route('/')
def index():
    return render_template(iid)

def gen(camera):
    while True:
        frame = camera.get_frame()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(gen(video_stream),
            mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    args = my_parser.parse_args()
    portid = args.port
    indexid = args.HTMLIndexID
    selfhosted = args.hosted

    if indexid <= 2:
        if indexid == 1:
            iid = 'index.html'
        elif indexid == 2:
            iid = 'index2.html'

    if selfhosted == True:
        hostname = socket.gethostname()
        IPAddr = socket.gethostbyname(hostname)
    else:
        IPAddr = '127.0.0.1'

    app.run(host=IPAddr,port=portid)
