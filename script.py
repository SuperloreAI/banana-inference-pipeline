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
import base64
from io import BytesIO
from PIL import Image, ImageDraw, ImageOps
from google.cloud import storage
import json
from app import load_model_by_url
import asyncio

client = None

sd_webui_dir = "/app/stable-diffusion-webui"
config_file = os.path.join(sd_webui_dir, "config.json")
temp_work_dir = "/app/temp_work_files"
output_bucket = "superlore-creative-runs-356405"
secret_file = "/app/.secrets.json"
secret_file_tmp = "/app/.secrets_temp.json"  # Hack work around
frame_wildcard = "Frame-%05d.png"
animation_frame_folder = "animation_frames"
frames_raw_folder = "frames_raw"
video_folder = "video"
default_fps = 30

secret = {
  "type": "service_account",
  "project_id": "superlore-demo",
  "private_key_id": "892e164b068652a2587cfeb6a2a08a2b5877f50a",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC5vMw9rwGQTl3i\nSXJbuXEOWv/Zk88SCnkuXmSNNynZl9ncrg0RBEZHglo5S0LryUbZ0Y7APcwXQBWX\nvGSTY1deDlqyY9dvRPe51sEvuGmbHiVB00FltwSbwRIuI8t2PLHOIcayX/Kgfi5z\nUavosWE5xbp0HzNSlbVUaczmpYYbFrsRmgl3A41M+bFtbgybjXzlb7+QCNWdrfyW\n0Ucg6Q74Ao6k2Vs1F161N5i5L2x3UXvwyCZeedwChrZwVAMBCnVoX8oc4rGFo+MY\nKRjcLK7lHUw0ZH3m/iMaSN+t3sjHUkOoVdBw4XtN5S1Ua7FNRcZLRDa3pZASixYi\nQiiWs5EXAgMBAAECggEACXdBwXMF1WDpD/tGRL5ysJSarXAHAZhfDKnq3feNvnUq\nuUB1kgRxwHs4NetMAdBEOB2h9NIxcI3ni9AiIBDUBwscPDMya41MQsBbIB954lnq\n9CvcDV8CcR2p24gfemsldKfsBHM3Xk6P93iWFknT9qnJEtn0N6VBlIe/1ZFiAEdV\n3O3nyoEKIl/4ifCGagm4RyGwyeyGlM70m7k3BOAFFCO/YR2rxnnQyHJ885WlBDsq\nM2cYJr/9AdQgwgDPxQWNy0OSwe1lD8lgTteQhDS693uHnTZc9qp7gLAclY2DAfHS\nk/XvTlR5VM8yykXBsxfZtEuGJZxNbQtwo6/TR1BTgQKBgQD5GdpHxX9RMIyidGMl\nvbjDklUfFc0nPxLF7lqu3cven0hlo2l9rfCywo6dDWUbBlHxlXRX//jgbjKPURZ3\nLW7SHpIOOZPHaJyFDGotnjE/oVwpT2lLf+DP+dVnKTRplka5lCI1vRIXiaLnE35+\n3zIv9bZbBfiVcSKFgW+w1RAa8QKBgQC+4bFKtNNJCFYl0gZGobrLCplA2hgUDdsu\ne0FYVPg/qejMWadKDGT3Md9yxkOuMYVVHtSbVZokN1iNqk9/uqxIyFG3yYsVQGfv\nWe9op1o7veQoDK+cGKu4q6vJBeJvLP7t47i4HUr4XOYFwfUrnrR79OKYdu4Mnam9\nJnVYPnMchwKBgQDGwvcmD5Ogb/G3atD1+2VjP+8Fx7qT10Mehir7nuSedVAqMXLq\nIpGNwapT7K1BHBDkiFF2KjwmsCdNrfEUFT95D4WRLiYZlgJWM2rBjZlUYWeNWtz0\nrkvvBzVdhEZa/drfFzEY2g2GlH9UjHyBtYxxMklYZfJNJCHcj0RUwB2CsQKBgA8p\nsoGyt433oZBDjMgTlNkIMIBcUslVCHI6zEgOB+JWxu1kuctCDMsuJQfjBAFUYbkP\nR+hG9oWl99zZCJOm6oSllQg6dFft09PJmyD/GkXgob0ktNZ7hziWOoEvfHtEYcPX\n8RZ/DTOJfaQ7chRS+RdXrqBZ4jMSWydxZKTr4Q0FAoGAe1KMroRhiHNeYtIMZwPP\ny0lgdJuxQzFN3B9qdR9HK/4+LM9pSvj9QTgBdsZaEBLUSiqUTToCrWfNVZmtCkdP\nwtLHgLLoCq0p1/SZgj3dAURl8T1Zww55LIKt7J2E+htNOReWQNJMqmoY3tY3WMcs\n9FbvqUm2K8cVr5O6bAldZKc=\n-----END PRIVATE KEY-----\n",
  "client_email": "inference-machines@superlore-demo.iam.gserviceaccount.com",
  "client_id": "101934595030530880425",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/inference-machines%40superlore-demo.iam.gserviceaccount.com"
}

# # Create a client object using the credentials from the JSON key file
# gcp_client = storage.Client.from_service_account_json(secret_file_tmp)
gcp_client = storage.Client.from_service_account_info(secret)


def write_to_gcp(local_filepath, output_filepath, bucket_name=output_bucket):
    # # Get a bucket object
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


def create_video(frames_dir, output_dir, fps=30):
    # Validate the input parameters
    if not os.path.isdir(frames_dir):
        raise ValueError(f'{frames_dir} is not a valid directory')
    if not os.path.isdir(output_dir):
        raise ValueError(f'{output_dir} is not a valid directory')
    if not isinstance(fps, int) or fps <= 0:
        raise ValueError(f'fps must be a positive integer value')

    # Create the temporary directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Define the command to create a video from the frames
    # Important: Be sure to sanitize all inputs
    print('calling ffmpeg on video frames')
    output_file = shlex.quote(os.path.join(output_dir, 'output.mp4'))
    cmd = f'ffmpeg -r {fps} -i {shlex.quote(os.path.join(frames_dir, frame_wildcard))} -c:v libx264 -crf 25 -profile:v high -pix_fmt yuv420p {output_file}'

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
        run_params = await prepare_inference(run_asset_dir, request)
        task = asyncio.create_task(inference(run_uuid, run_asset_dir, run_params))
        # result = await inference(run_uuid, run_asset_dir, request)
        # Return an immediate response to the client with the run_id
        return {'run_id': str(run_uuid), 'status': 'running'}
    except Exception as e:
        print(f'An error occurred: {type(e).__name__} - {str(e)}')
        err = e
        result = None
        # on error, lets generate a video of everything we've got so far

        try:
            anim_frame_dir = os.path.join(run_asset_dir, animation_frame_folder)
            if os.listdir(anim_frame_dir) > 0:
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


async def prepare_inference(run_asset_dir, request: Request):
    global client
    
    body = await request.body()
    model_input = json.loads(body)

    if not ('video_file' in model_input):
        print('video_file is not in request... exiting...')
        raise ValueError("video_file is required")

    if not ("params" in model_input):
        print('params is not in request... exiting...')
        raise ValueError("params is required")

    # see if valid controlnet config 
    # controlnet modules 
    cn_module_availability_raw = client.get('/controlnet/module_list')
    cn_module_availability = cn_module_availability_raw.json().get('module_list', [])

    # controlnet models
    cn_model_availability_raw = client.get('/controlnet/model_list')
    cn_model_availability = cn_model_availability_raw.json().get('model_list', [])

    # print('controlnet module availability: ', ', '.join(cn_module_availability))
    # print('controlnet model availability: ', ', '.join(cn_model_availability))

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

    # sort out our base params
    # default to 512x512 if not specified (SD 1.5)
    if 'width' not in params:
        params['width'] = 512
    if 'height' not in params:
        params['height'] = 512


    # # update the config for multi controlnet
    # print('updating config file', config_file)
    # print('config exists', os.path.isfile(config_file))
    # if not os.path.isfile(config_file):
    #     print('config file does not exist - exiting')
    #     print('dir listing', os.listdir(sd_webui_dir))
    #     print('ui config?', os.path.isdir(os.path.join(sd_webui_dir, 'ui-config.json')))
    #     return
    
    # with open(config_file, 'r') as f:
    #     config = json.load(f)

    # print('found config', config)

    # config['control_net_model_cache_size'] = 10
    # config['control_net_max_models_num'] = 6

    # print('updated config', config)

    # with open(config_file, 'w') as f:
    #     json.dump(config, f)

    if 'model_url' in model_input:
        print('loading model from url', model_input['model_url'])
        # download model
        load_model_by_url(model_input['model_url'])

    # read the video file
    tmp_video_path = download_video(model_input['video_file'], run_asset_dir)
    frame_dir = os.path.join(run_asset_dir, frames_raw_folder)
    os.makedirs(frame_dir)
    # split video file into frames
    video_frame_dir = split_video_frames(tmp_video_path, frame_dir, fps=default_fps)

    reference_imgs = [os.path.join(frame_dir, x) for x in
                      sorted(os.listdir(frame_dir), key=numerical_part)]
    
    if len(reference_imgs) > 2000:
        raise ValueError(f"too many frames in video - must be less than 2000 at 30FPS (received {len(reference_imgs)})")    

    return model_input

"""
API request body:
{
    "video_file": "https://storage.googleapis.com/superlore-video-sources-738437/demo-man.mp4",
    "loopback_souce": "PreviousFrame", # (Optional)
    "save_image_samples": 1,  # saves a sample image every N frames (Optional)
    "save_video_samples": 1,  # saves a sample video every N frames (Optional)
    "model_url": "https://huggingface.co/Superlore/toolguru-modi-sd15/blob/main/ToolGuru7ModernDisney_5760_lora-002-001.safetensors",  # (Optional)
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
async def inference(run_id, run_asset_dir, model_input):
    global client
    if not ("loopback_souce" in model_input):
        loopback_souce = 'PreviousFrame'
    else:
        loopback_souce = model_input['loopback_souce']

    save_image_samples = model_input.get('save_image_samples', -1)
    save_video_samples = model_input.get('save_video_samples', -1)

    params = model_input['params']

    source_frame_dir = os.path.join(run_asset_dir, frames_raw_folder)
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

    reference_imgs = [os.path.join(source_frame_dir, x) for x in
                      sorted(os.listdir(source_frame_dir), key=numerical_part)]

    print(f'starting inference... processing {len(reference_imgs)} images')

    loops = len(reference_imgs)


    for i in range(loops):
        if i > 6:
            # TODO: remove after dev
            print('DEV BREAKING EARLY')
            break 

        print(f'processing frame {i + 1} of {loops}')
        frame_params = params.copy()
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

                latent_mask = Image.new("RGB", (working_width, height), "black")
                latent_draw = ImageDraw.Draw(latent_mask)
                latent_draw.rectangle((initial_width, 0, initial_width * 2, height), fill="white")

                frame_params['mask'] = b64_encode(latent_mask)
                frame_params['init_images'] = [b64_encode(img) for img in init_images]
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
                    control_units = frame_params['alwayson_scripts']['controlnet']['args']
                    for ii in range(len(frame_params['alwayson_scripts']['controlnet']['args'])):
                        if not isinstance(frame_params['alwayson_scripts']['controlnet']['args'][ii], dict):
                            continue
                        frame_params['alwayson_scripts']['controlnet']['args'][ii]['input_image'] = b64_encode(cn_input)

                latent_mask = Image.new("RGB", (working_width, height), "black")
                latent_draw = ImageDraw.Draw(latent_mask)
                latent_draw.rectangle((initial_width, 0, working_width, height), fill="white")

                frame_params['mask'] = b64_encode(latent_mask)
                frame_params['init_images'] = [b64_encode(img) for img in init_images]
        else:
            print('first frame....')
            # first frame - we use txt2img
            endpoint = 'txt2img'

            latent_mask = Image.new("RGB", (initial_width, height), "white")
            frame_params['mask'] = b64_encode(latent_mask)

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

        generate_samples = save_image_samples > 0 and i % save_image_samples == 0
        generate_video_sample = save_video_samples > 0 and i % save_video_samples == 0
        # dev save image locally + upload to google storage
        if generate_samples:
            g_sample_filename_local = os.path.join(frame_dir, f'grid_{i}.png')
            g_sample_filename_output_path = f'{run_id}/{animation_frame_folder}/grid_{i}.png'
            processed_image.save(g_sample_filename_local)
            write_to_gcp(g_sample_filename_local, g_sample_filename_output_path)
            f_sample_filename_local = os.path.join(frame_dir, f'frame_{i}.png')
            f_sample_filename_output_path = f'{run_id}/{animation_frame_folder}/frame_{i}.png'
            init_img.save(f_sample_filename_local)
            write_to_gcp(f_sample_filename_local, f_sample_filename_output_path)
        if generate_video_sample: 
            output_video_local_path = create_video(frame_dir, os.path.join(video_dir, 'Sample-{i:04d}.mp4'), default_fps)
            output_video_sample_path = f'{run_id}/{video_folder}/Sample-{i:04d}.mp4'
            write_to_gcp(output_video_local_path, output_video_sample_path)

        # Sort out the third_frame_image
        if i == 0:
            # Default FirstGen
            third_image = init_img
            third_image_index = 0

        init_images = [init_img]

        # TODO: support historical 3rd frame etc...

        history.append(init_img)

    print('done! no errors')

    return {"done": True}

on_app_started(register_endpoints)
