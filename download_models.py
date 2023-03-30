import os
import requests
import sys
import time
from tqdm import tqdm
from typing import Union
from urllib.parse import urlparse

MODEL_URL = os.environ.get('MODEL_URL')
HF_TOKEN = os.environ.get('HF_TOKEN', '')
CONTROLNET_MODEL_URLS = os.environ.get('CONTROLNET_MODEL_URLS', []).split(',')

CHUNK_SIZE = 1024 * 1024

def get_filename(model_url, id="model", path="models/Stable-diffusion/"):
    if '.safetensors' in model_url:
        return path + id + '.safetensors'
    if '.pth' in model_url:
        return path + id + '.pth'
    else:
        return path + id + '.ckpt'

def check_model_file(filename):
    file_size_mb = round(os.path.getsize(filename) / (1024 * 1024))
    if file_size_mb < 100:
        print(f'The downloaded file is only {file_size_mb} MB and does not appear to be a valid model.')
        sys.exit(1)

def download_hf_file(model_url, HF_TOKEN, id="model", path="models/Stable-diffusion/"):
    filename = get_filename(model_url, id, path)
    if os.path.exists(filename):
        return
    print("Model URL:", model_url)
    print("Download Location:", filename)
    if not HF_TOKEN:
        print("A Huggingface token was not provided.")
    else:
        print("Using Huggingface authentication token.")
    headers = {'Authorization': f'Bearer {HF_TOKEN}'}
    response = requests.get(model_url, headers=headers, stream=True)
    response.raise_for_status()
    with open(filename, 'wb') as f, tqdm(desc="Downloading", unit="bytes", total=int(response.headers.get('content-length', 0))) as progress:
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            if chunk:
                f.write(chunk)
                progress.update(len(chunk))
    check_model_file(filename)

def download_other_file(model_url, id="model", path="models/Stable-diffusion/"):
    filename = get_filename(model_url, id, path)
    if os.path.exists(filename):
        return
    print("Model URL:", model_url)
    print("Download Location:", filename)
    response = requests.get(model_url, stream=True)
    response.raise_for_status()
    with open(filename, 'wb') as f, tqdm(desc="Downloading", unit="bytes", total=int(response.headers.get('content-length', 0))) as progress:
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            if chunk:
                f.write(chunk)
                progress.update(len(chunk))
    check_model_file(filename)

def download(url, id="model", path="models/Stable-diffusion/"):
    if 'huggingface.co' in url:
        if '/blob/' in url:
            url = url.replace('/blob/', '/resolve/')
        download_hf_file(url, HF_TOKEN, id, path)
    else:
        download_other_file(url, id, path)

if __name__ == '__main__':
    download(MODEL_URL, "model", "models/Stable-diffusion/")
    for i, url in enumerate(CONTROLNET_MODEL_URLS):
        print('Downloading controlnet model', i, url)
        # Model name becomes the model ID
        # Get the filename with extension from the URL
        filename_with_ext = os.path.basename(urlparse(url).path)

        # Get the filename without extension
        filename_without_ext, _ = os.path.splitext(filename_with_ext)
        download(url, filename_without_ext, path="models/ControlNet/")