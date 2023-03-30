import json
import os
import requests
import subprocess
from fastapi import FastAPI, Request, Body, HTTPException
from fastapi.testclient import TestClient
from modules.script_callbacks import on_app_started
import subprocess
import shlex
import uuid
import shutil

client = None

temp_work_dir = "/app/temp_work_files"

def healthcheck():
    gpu = False
    out = subprocess.run("nvidia-smi", shell=True)
    if out.returncode == 0: # success state on shell command
        gpu = True
    return {"state": "healthy", "gpu": gpu}


def download_video(url, output_dir):
    print(f'downloading video {url}')
    r = requests.get(url, allow_redirects=True)
    filename = os.path.join(output_dir, 'video.mp4')
    open(filename, 'wb').write(r.content)
    print('download complete', os.listdir(output_dir))
    return filename


def split_video_frames(video_file, output_dir, fps=30):
    # Validate the input parameters
    if not os.path.isfile(video_file):
        raise ValueError(f'{video_file} is not a valid file')
    if not os.path.isdir(output_dir):
        raise ValueError(f'{output_dir} is not a valid directory')
    if not isinstance(fps, int) or fps <= 0:
        raise ValueError(f'fps must be a positive integer value')

    # Create the temporary directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Define the command to extract frames from the video
    # Important: Be sure to sanitize all inputs
    print('calling ffmpeg on video frames')
    cmd = f'ffmpeg -i {shlex.quote(video_file)} -r {fps} {shlex.quote(os.path.join(output_dir, "Frame-%05d.png"))}'

    # Execute the command using subprocess
    subprocess.call(cmd, shell=True)

    return output_dir


# Define a key function to extract the numerical part of the filename
# Important: filename should be like /someFile-00123.png
# Example usage:
# sorted_files = sorted(files, key=numerical_part)
def numerical_part(filename):
    # Find the index of the first digit in the filename
    index = next((i for i, c in enumerate(filename) if c.isdigit()), None)
    if index is not None:
        # Extract the numerical part of the filename
        return int(filename[index:].split(".")[0])
    else:
        # If the filename doesn't contain any digits, return 0
        return 0


def register_endpoints(block, app):
    global client
    app.add_api_route('/healthcheck', healthcheck, methods=['GET'])
    app.add_api_route('/', inference_handler, methods=['POST'])
    client = TestClient(app)


async def inference_handler(request: Request):
    global client
    print('received inference request...')

    # Generate a random UUID
    run_uuid = uuid.uuid4()
    print(f'using run ID {run_uuid}')
    run_asset_dir = os.path.join(temp_work_dir, str(run_uuid))
    os.makedirs(run_asset_dir)
    print(f'run tmp dir {run_asset_dir}')

    try:
        result = await inference(run_uuid, run_asset_dir, request)
        err = None
    except Exception as e:
        print(f'An error occurred: {type(e).__name__} - {str(e)}')
        err = e
        result = None

    # Clean up - deletes the asset dir
    print(f'cleaning up folder {run_asset_dir}')
    shutil.rmtree(run_asset_dir)

    if err is not None:
        raise HTTPException(status_code=500, detail=str(err))

    return result


async def inference(run_id, run_asset_dir, request: Request):
    global client
    body = await request.body()
    model_input = json.loads(body)

    if not ('video_file' in model_input):
        print('video_file is not in request... exiting...')
        raise ValueError("video_file is required")

    # read the video file
    tmp_video_path = download_video(model_input['video_file'], run_asset_dir)
    frame_dir = os.path.join(run_asset_dir, 'frames_raw')
    os.makedirs(frame_dir)
    # split video file into frames
    video_frame_dir = split_video_frames(tmp_video_path, frame_dir, fps=30)

    # run the main script
    """
    how it works (please review https://xanthius.itch.io/multi-frame-rendering-for-stablediffusion)
    1) txt 2 img on the first frame 
    2) img2img on 2nd frame (with the first frame beside it)
    3) img2img on Nth frame (with previous frame + reference frame beside it) 
    
    This will write animation frames to the temp output directory
    After all frames processed, it will use ffmpeg to make them a video
    Then saves the video to google storage
    """

    reference_imgs = [os.path.join(frame_dir, x) for x in
                      sorted(os.listdir(frame_dir), key=numerical_part)]

    print(f'starting inference... processing {len(reference_imgs)} images')

    loops = len(reference_imgs)

    params = None
    mode = 'default'

    if 'endpoint' in model_input:
        endpoint = model_input['endpoint']
        if 'params' in model_input:
            params = model_input['params']
    else:
        mode = 'banana_compat'
        endpoint = 'txt2img'
        params = model_input

    if endpoint == 'txt2img' or endpoint == 'img2img':
        if 'width' not in params:
            params['width'] = 768
        if 'height' not in params:
            params['height'] = 768

    if endpoint == 'txt2img':
        if 'num_inference_steps' in params:
            params['steps'] = params['num_inference_steps']
            del params['num_inference_steps']
        if 'guidance_scale' in params:
            params['cfg_scale'] = params['guidance_scale']
            del params['guidance_scale']

    if params is not None:
        response = client.post('/sdapi/v1/' + endpoint, json = params)
    else:
        response = client.get('/sdapi/v1/' + endpoint)

    output = response.json()

    if mode == 'banana_compat' and 'images' in output:
        output = {
            "base64_output": output["images"][0]
        }

    output["callParams"] = params

    return output

on_app_started(register_endpoints)