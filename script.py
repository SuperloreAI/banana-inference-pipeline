import json
import os
import requests
import subprocess
from fastapi import FastAPI, Request, Body, HTTPException, BackgroundTasks
from fastapi.testclient import TestClient
from modules.script_callbacks import on_app_started
import subprocess
import shlex
import uuid
import shutil
import base64
from io import BytesIO
from PIL import Image, ImageDraw, ImageOps
from google.cloud import storage
import json
from app import load_model_by_url
import asyncio
import re
import datetime
import copy

client = None

sd_webui_dir = "/app/stable-diffusion-webui"
config_file = os.path.join(sd_webui_dir, "config.json")
temp_work_dir = "/app/temp_work_files"
output_bucket = "superlore-creative-runs-356405"
# secret_file = "/app/.secrets.json"
secret_json_data = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
frame_wildcard = "Frame-%05d.png"
animation_frame_folder = "animation_frames"
frames_raw_folder = "frames_raw"
video_folder = "video"
default_fps = 30
base_temporal_config = {
    "model": "diff_control_sd15_temporalnet_fp16 [adc6bd97]",
    "module": "none",
    "weight": 1,
    "guidance": 1,
}

# Parse the JSON data
secret_data = json.loads(secret_json_data.replace('\n', '\\n'))

# gcp_client = storage.Client.from_service_account_json(secret_file)
gcp_client = storage.Client.from_service_account_info(secret_data)


def write_to_gcp(local_filepath, output_filepath, bucket_name=output_bucket):
    # Get a bucket object
    bucket = gcp_client.get_bucket(bucket_name)

    # Create a blob object for the file
    blob = bucket.blob(output_filepath)

    # Upload the file to the bucket
    blob.upload_from_filename(local_filepath)

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
    cmd = f'ffmpeg -i {shlex.quote(video_file)} -r {fps} {shlex.quote(os.path.join(output_dir, frame_wildcard))}'

    # Execute the command using subprocess
    subprocess.call(cmd, shell=True)

    return output_dir


def create_video(frames_dir, output_file, fps=30):
    # Validate the input parameters
    if not os.path.isdir(frames_dir):
        raise ValueError(f'{frames_dir} is not a valid directory')
    if not os.path.isdir(os.path.dirname(output_file)):
        raise ValueError(f'{os.path.dirname(output_file)} is not a valid directory')
    if not isinstance(fps, int) or fps <= 0:
        raise ValueError(f'fps must be a positive integer value')

    # Create the temporary directory if it doesn't exist
    if not os.path.exists(os.path.dirname(output_file)):
        os.makedirs(os.path.dirname(output_file))

    # Define the command to create a video from the frames
    # Important: Be sure to sanitize all inputs
    cmd = f'ffmpeg -r {fps} -i {shlex.quote(os.path.join(frames_dir, frame_wildcard))} -c:v libx264 -crf 25 -profile:v high -pix_fmt yuv420p {shlex.quote(output_file)}'

    # Execute the command using subprocess
    subprocess.call(cmd, shell=True)

    return output_file


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
    cmd = f'ffmpeg -i {shlex.quote(video_file)} -r {fps} {shlex.quote(os.path.join(output_dir, frame_wildcard))}'

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

def convert_b64_image(encoded_image):
    image_data = base64.b64decode(encoded_image)
    image = Image.open(BytesIO(image_data))
    return image

def b64_encode(image):
    buffer = BytesIO()
    image.save(buffer, format='JPEG')
    img_str = base64.b64encode(buffer.getvalue())
    return img_str.decode('utf-8')


def open_image(image_path, w, h):
    image = Image.open(image_path).convert("RGB").resize((w, h), Image.ANTIALIAS)
    return image

def is_valid_bucket_folder_name(name):
    # Bucket folder name must be between 1 and 1024 characters
    if len(name) < 1 or len(name) > 1024:
        return False
    # Bucket folder name can only contain letters, numbers, dashes, underscores, and dots
    pattern = re.compile(r'^[a-zA-Z0-9_\-\.]+$')
    if not pattern.match(name):
        return False
    # Bucket folder name cannot start or end with a dash
    if name.startswith('-') or name.endswith('-'):
        return False
    return True

async def inference_handler(request: Request):
    global client
    print('received inference request')

    # Generate a random UUID
    run_uuid = uuid.uuid4()
    print(f'using run ID {run_uuid}')
    run_asset_dir = os.path.join(temp_work_dir, str(run_uuid))
    os.makedirs(run_asset_dir)
    print(f'run tmp dir {run_asset_dir}')
    err = None
    result = {'status': 'ok'}

    try:
        result = await inference(run_uuid, run_asset_dir, request)
        # Return an immediate response to the client with the run_id
    except Exception as e:
        print(f'An error occurred: {type(e).__name__} - {str(e)}')
        err = e
        result = None
        # on error, lets generate a video of everything we've got so far

        try:
            anim_frame_dir = os.path.join(run_asset_dir, animation_frame_folder)
            if len(os.listdir(anim_frame_dir)) > 0:
                print('generating video from frames')
                video_dir = os.path.join(run_asset_dir, video_folder)
                video_file_local_path = create_video(anim_frame_dir, video_dir, default_fps)
                output_video_sample_path = f'{run_uuid}/{video_folder}/Sample-error.mp4'
                write_to_gcp(video_file_local_path, output_video_sample_path)
        except Exception as e:
            print(f'An error occurred: {type(e).__name__} - {str(e)}')
    
        result = {'status': 'error', 'error': 'An error occurred while preparing the inference'}
        
    # Clean up - deletes the asset dir
    print(f'cleaning up folder {run_asset_dir}')
    shutil.rmtree(run_asset_dir)

    if err is not None:
        raise HTTPException(status_code=500, detail=str(err))

    return result

"""
API request body:
{
    "video_file": "https://storage.googleapis.com/superlore-video-sources-738437/demo-man.mp4",
    "loopback_souce": "PreviousFrame", # (Optional)
    "max_frames": 10,  # only process a sample -> leave out to process the whole video
    "save_image_samples": 1,  # saves a sample image every N frames (Optional)
    "save_video_samples": 1,  # saves a sample video every N frames (Optional)
    "model_url": "https://huggingface.co/Superlore/toolguru-modi-sd15/blob/main/ToolGuru7ModernDisney_5760_lora-002-001.safetensors",  # (Optional)
    "bucket_output_folder": "newton", # (Optional) where you will find your output files 
    "params": {
        "prompt": "a beautiful woman",
        "negative_prompt": "",
        "width": 512,
        "height": 512,
        "denoising_strength": 0.9,
        "cfg_scale": 7,
        "seed": -1,
        "steps": 20,
        "restore_faces": false,
        "sampler_index": "Euler a",
        "alwayson_scripts": {
            "controlnet": {
                "args": [
                    {
                        "input_image": "base64...",  # Added in via script
                        "module": "canny",
                        "model": "control_sd15_canny",
                        "weight": 1,
                        "resize_mode": 0,
                        "processor_res": 512,
                        "guidance_start": 0, 
                        "guidance_end": 1,
                        "threshold_a": 100,
                        "threshold_b": 200,
                    },
                    {
                        "input_image": "base64...",  # Added in via script
                        "model": "diff_control_sd15_temporalnet_fp16 [adc6bd97]",
                        "module": "none",
                        "weight": 1,
                        "guidance": 1,
                    }
                ]
            }
        }
    }
}
Notes:

"resize_mode" : how to resize the input image so as to fit the output resolution of the generation. defaults to "Scale to Fit (Inner Fit)". Accepted values:
    0 or "Just Resize" : simply resize the image to the target width/height
    1 or "Scale to Fit (Inner Fit)" : scale and crop to fit smallest dimension. preserves proportions.
    2 or "Envelope (Outer Fit)" : scale to fit largest dimension. preserves proportions
"""
async def inference(run_id, run_asset_dir, request):
    global client
        
    body = await request.body()
    model_input = json.loads(body)

    #############################################
    # Form Validation ###########################
    #############################################

    if not ('video_file' in model_input):
        print('video_file is not in request... exiting...')
        raise ValueError("video_file is required")

    if not ("params" in model_input):
        print('params is not in request... exiting...')
        raise ValueError("params is required")
    
    if not ("bucket_output_folder" in model_input):
        print('bucket_output_folder is not in request... exiting...')
        raise ValueError("bucket_output_folder is required")
    
    if not is_valid_bucket_folder_name(model_input['bucket_output_folder']):
        print('bucket_output_folder is not valid... exiting...')
        raise ValueError("bucket_output_folder is not valid")
    
    video_file_name, _ = os.path.splitext(os.path.basename(model_input['video_file']))
    current_date = datetime.datetime.now().date()
    formatted_date = current_date.strftime("%m_%d_%Y")
    output_bucket_path = f"{model_input['bucket_output_folder']}/{video_file_name}-{formatted_date}/{run_id}"
    
    # see if valid controlnet config 
    # controlnet modules 
    cn_module_availability_raw = client.get('/controlnet/module_list')
    cn_module_availability = cn_module_availability_raw.json().get('module_list', [])

    # controlnet models
    cn_model_availability_raw = client.get('/controlnet/model_list')
    cn_model_availability = cn_model_availability_raw.json().get('model_list', [])

    if 'alwayson_scripts' in model_input['params']:
        if 'controlnet' in model_input['params']['alwayson_scripts']:
            # check if the module is available
            control_units = model_input['params']['alwayson_scripts']['controlnet']['args']
            if any(not (s['module'] in cn_module_availability) for s in control_units):
                raise ValueError("controlnet module is not available")
            # check if the model is available
            if any(not (s['model'] in cn_model_availability) for s in control_units):
                raise ValueError("controlnet model is not available")

    params = model_input['params']

    # Default some params that are important if not included in the request

    # default to 512x512 if not specified (SD 1.5)
    if 'width' not in params:
        params['width'] = 512
    if 'height' not in params:
        params['height'] = 512
    if 'inpainting_fill' not in params:
        params['inpainting_fill'] = 1
    if 'initial_noise_multiplier' not in params:
        params['initial_noise_multiplier'] = 1
    if 'inpaint_full_res' not in params:
        params['inpaint_full_res'] = 0
    if 'inpaint_full_res_padding' not in params:
        params['inpaint_full_res_padding'] = 0

    use_temporal_net = True
    if 'use_temporal_net' in params:
        use_temporal_net = params['use_temporal_net']
    
    # for each controlnet unit, we should set guess_mode = False
    if 'alwayson_scripts' in params and 'controlnet' in params['alwayson_scripts']:
        for ii in range(len(params['alwayson_scripts']['controlnet']['args'])):
            if not isinstance(params['alwayson_scripts']['controlnet']['args'][ii], dict):
                continue
            if 'guess_mode' not in params['alwayson_scripts']['controlnet']['args'][ii]:
                params['alwayson_scripts']['controlnet']['args'][ii]['guess_mode'] = False

    #############################################
    # Video Preprocess ##########################
    #############################################

    # read the video file
    tmp_video_path = download_video(model_input['video_file'], run_asset_dir)
    source_frame_dir = os.path.join(run_asset_dir, frames_raw_folder)
    os.makedirs(source_frame_dir)
    # split video file into frames
    split_video_frames(tmp_video_path, source_frame_dir, fps=default_fps)

    reference_imgs = [os.path.join(source_frame_dir, x) for x in
                    sorted(os.listdir(source_frame_dir), key=numerical_part)]
    
    if len(reference_imgs) > 2000:
        raise ValueError(f"too many frames in video - must be less than 2000 at 30FPS (received {len(reference_imgs)})")    
    
    #############################################
    # Load model ################################
    #############################################

    if 'model_url' in model_input:
        print('loading model from url', model_input['model_url'])
        # download model
        load_model_by_url(model_input['model_url'])

    #############################################
    # Script logic ##############################
    #############################################

    if not ("loopback_souce" in model_input):
        loopback_souce = 'PreviousFrame'
    else:
        loopback_souce = model_input['loopback_souce']

    save_image_samples = model_input.get('save_image_samples', -1)
    save_video_samples = model_input.get('save_video_samples', -1)

    frame_dir = os.path.join(run_asset_dir, animation_frame_folder)
    video_dir = os.path.join(run_asset_dir, video_folder)
    if not os.path.isdir(frame_dir):
        os.makedirs(frame_dir)
    if not os.path.isdir(video_dir):
        os.makedirs(video_dir)

    initial_width = params['width']
    height = params['height']
    third_image = None
    third_image_index = 0
    history = []

    print(f'starting inference... processing {len(reference_imgs)} images')

    loops = len(reference_imgs)

    for i in range(loops):
        if "max_frames" in model_input and isinstance(model_input['max_frames'], int) and i > model_input['max_frames']:
            # TODO: remove after dev
            print('done according to max_frames')
            break 

        print(f'processing frame {i + 1} of {loops}')
        frame_params = copy.deepcopy(params)
        endpoint = 'img2img'

        # ref_image = Image.open(reference_imgs[i]).convert("RGB").resize((initial_width, height), Image.ANTIALIAS)
        ref_image = open_image(reference_imgs[i], initial_width, height)
        
        if (i > 0):
            # init_images initialized at end of first loop
            loopback_image = init_images[0]  # AKA historical option
            if loopback_souce == "FirstGen":
                loopback_image = history[0]
            elif loopback_souce == "InputFrame":
                loopback_image = ref_image

            if i > 1:
                # 3 frame comparison
                working_width = initial_width * 3
                img = Image.new("RGB", (working_width, height))
                img.paste(init_images[0], (0, 0))
                # img.paste(p.init_images[0], (initial_width, 0))
                img.paste(loopback_image, (initial_width, 0))
                img.paste(third_image, (initial_width * 2, 0))
                init_images = [img]  # pass in 3 frames

                # TODO add color correction
                # if color_correction_enabled:
                #     p.color_corrections = [processing.setup_color_correction(img)]

                # add the control net inputs
                cn_input = Image.new("RGB", (working_width, height))
                cn_input.paste(open_image(reference_imgs[i - 1], initial_width, height), (0, 0))
                cn_input.paste(ref_image, (initial_width, 0))
                cn_input.paste(open_image(reference_imgs[third_image_index], initial_width, height), (initial_width * 2, 0))
                if 'alwayson_scripts' in frame_params and 'controlnet' in frame_params['alwayson_scripts']:
                    for ii in range(len(frame_params['alwayson_scripts']['controlnet']['args'])):
                        if not isinstance(frame_params['alwayson_scripts']['controlnet']['args'][ii], dict):
                            continue
                        frame_params['alwayson_scripts']['controlnet']['args'][ii]['input_image'] = b64_encode(cn_input)
                    
                    if use_temporal_net:
                        # add temporal net inputs
                        temporal_input = Image.new("RGB", (working_width, height))
                        temporal_input.paste(init_images[0], (0, 0))
                        temporal_input.paste(init_images[0], (initial_width, 0))
                        temporal_input.paste(third_image, (initial_width * 2, 0))
                        frame_params['alwayson_scripts']['controlnet']['args'].append({
                          "input_image": b64_encode(temporal_input),  
                          **base_temporal_config
                        })


                latent_mask = Image.new("RGB", (working_width, height), "black")
                latent_draw = ImageDraw.Draw(latent_mask)
                latent_draw.rectangle((initial_width, 0, initial_width * 2, height), fill="white")

                frame_params['mask'] = b64_encode(latent_mask)
                frame_params['init_images'] = [b64_encode(img) for img in init_images]
                frame_params['width'] = working_width
            else:
                # 2 frame comparison
                working_width = initial_width * 2
                img = Image.new("RGB", (working_width, height))
                img.paste(init_images[0], (0, 0))
                img.paste(loopback_image, (initial_width, 0))
                init_images = [img]

                # TODO add color correction
                # if color_correction_enabled:
                #     p.color_corrections = [processing.setup_color_correction(img)]

                # # add the control net inputs
                cn_input = Image.new("RGB", (working_width, height))
                cn_input.paste(open_image(reference_imgs[i - 1], initial_width, height), (0, 0))
                cn_input.paste(ref_image, (initial_width, 0))
                if 'alwayson_scripts' in frame_params and 'controlnet' in frame_params['alwayson_scripts']:
                    for ii in range(len(frame_params['alwayson_scripts']['controlnet']['args'])):
                        if not isinstance(frame_params['alwayson_scripts']['controlnet']['args'][ii], dict):
                            continue
                        frame_params['alwayson_scripts']['controlnet']['args'][ii]['input_image'] = b64_encode(cn_input)
                    
                    if use_temporal_net:
                        # add temporal net inputs
                        temporal_input = Image.new("RGB", (working_width, height))
                        temporal_input.paste(init_images[0], (0, 0))
                        temporal_input.paste(init_images[0], (initial_width, 0))
                        frame_params['alwayson_scripts']['controlnet']['args'].append({
                          "input_image": b64_encode(temporal_input),  
                          **base_temporal_config
                        })

                latent_mask = Image.new("RGB", (working_width, height), "black")
                latent_draw = ImageDraw.Draw(latent_mask)
                latent_draw.rectangle((initial_width, 0, working_width, height), fill="white")

                frame_params['mask'] = b64_encode(latent_mask)
                frame_params['init_images'] = [b64_encode(img) for img in init_images]
                frame_params['width'] = working_width
        else:
            # first frame - we use txt2img
            endpoint = 'txt2img'

            latent_mask = Image.new("RGB", (initial_width, height), "white")
            frame_params['mask'] = b64_encode(latent_mask)
            frame_params['width'] = initial_width

            # add the control net inputs
            if 'alwayson_scripts' in frame_params and 'controlnet' in frame_params['alwayson_scripts']:
                for ii in range(len(frame_params['alwayson_scripts']['controlnet']['args'])):
                    if not isinstance(frame_params['alwayson_scripts']['controlnet']['args'][ii], dict):
                        continue
                    frame_params['alwayson_scripts']['controlnet']['args'][ii]['input_image'] = b64_encode(ref_image)

        # Call the webui API
        print('calling API...')
        response = client.post('/sdapi/v1/' + endpoint, json = frame_params)

        output = response.json()
        processed_image_b64 = output["images"][0]  # base 64 encoded
        processed_image = convert_b64_image(processed_image_b64)

        init_img = processed_image
        if (i > 0):
            init_img = init_img.crop((initial_width, 0, initial_width * 2, height))
        
        # save the file
        local_animation_frame_file = os.path.join(frame_dir, f'Frame-{i:05d}.png')
        init_img.save(local_animation_frame_file)

        generate_samples = save_image_samples > 0 and (i + 1) % save_image_samples == 0
        generate_video_sample = save_video_samples > 0 and (i + 1) % save_video_samples == 0
        # dev save image locally + upload to google storage
        if generate_samples:
            g_sample_filename_local = os.path.join(frame_dir, f'Grid-{i:05d}.png')
            g_sample_filename_output_path = f'{output_bucket_path}/{animation_frame_folder}/Grid-{i:05d}.png'
            processed_image.save(g_sample_filename_local)
            write_to_gcp(g_sample_filename_local, g_sample_filename_output_path)
            f_sample_filename_output_path = f'{output_bucket_path}/{animation_frame_folder}/Frame-{i:05d}.png'
            write_to_gcp(local_animation_frame_file, f_sample_filename_output_path)
        if generate_video_sample: 
            output_video_local_path = create_video(frame_dir, os.path.join(video_dir, f'Sample-{i:05d}.mp4'), default_fps)
            output_video_sample_path = f'{output_bucket_path}/{video_folder}/Sample-{i:05d}.mp4'
            write_to_gcp(output_video_local_path, output_video_sample_path)

        # Sort out the third_frame_image
        if i == 0:
            # Default FirstGen
            third_image = init_img
            third_image_index = 0

        init_images = [init_img]

        # TODO: support historical 3rd frame etc...

        history.append(init_img)

    output_video_sample_path = f'{output_bucket_path}/{video_folder}/animation_video.mp4'
    print('writting output video', output_video_sample_path)
    output_video_local_path = create_video(frame_dir, os.path.join(video_dir, 'animation_video.mp4'), default_fps)
    write_to_gcp(output_video_local_path, output_video_sample_path)

    return {"status": "success", "message": "done", "bucket_path": output_bucket_path}

on_app_started(register_endpoints)
