FROM nvidia/cuda:11.7.1-runtime-ubuntu22.04
  
# To use a different model, change the model URL below:
ARG MODEL_URL='https://huggingface.co/runwayml/stable-diffusion-v1-5/blob/main/v1-5-pruned-emaonly.ckpt'
# Array representation in a string of controlnet models
# Use a comma to separate the models [IMPORTANT]
ARG CONTROLNET_MODEL_URLS="\
    https://huggingface.co/lllyasviel/ControlNet/blob/main/models/control_sd15_openpose.pth,\
    https://huggingface.co/lllyasviel/ControlNet/blob/main/models/control_sd15_canny.pth,\
    https://huggingface.co/lllyasviel/ControlNet/blob/main/models/control_sd15_depth.pth,\
    https://huggingface.co/lllyasviel/ControlNet/blob/main/models/control_sd15_hed.pth,\
    https://huggingface.co/lllyasviel/ControlNet/blob/main/models/control_sd15_normal.pth"

ARG OPENPOSE_MODEL_URLS="\
    https://huggingface.co/lllyasviel/ControlNet/resolve/main/annotator/ckpts/hand_pose_model.pth,\
    https://huggingface.co/lllyasviel/ControlNet/resolve/main/annotator/ckpts/body_pose_model.pth"

ARG HED_URLS="\
    https://huggingface.co/lllyasviel/ControlNet/resolve/main/annotator/ckpts/network-bsds500.pth"

ARG DEPTH_LERES_MODEL_URLS="\
    https://cloudstor.aarnet.edu.au/plus/s/lTIJF4vrvHCAI31/download"

# If you are using a private Huggingface model (sign in required to download) insert your Huggingface
# access token (https://huggingface.co/settings/tokens) below:
ARG HF_TOKEN=''

ARG GCP_SERVICE_ACCOUNT_JSON=''

RUN apt update && apt-get -y install git wget \
    python3.10 python3.10-venv python3-pip \
    build-essential libgl-dev libglib2.0-0 vim \
    ffmpeg
RUN ln -s /usr/bin/python3.10 /usr/bin/python

RUN useradd -ms /bin/bash banana

WORKDIR /app

# newlines need to be escaped
# ARG ESCAPED_GCP_SERVICE_ACCOUNT_KEY=$(echo $GCP_SERVICE_ACCOUNT_KEY | sed 's/\\n/\\\\n/g')
# RUN echo "${ESCAPED_GCP_SERVICE_ACCOUNT_KEY}" > /app/.secrets.json
# RUN chmod 600 /app/.secrets.json

# used to store temporary files
RUN mkdir -p /app/temp_work_files

# SD Webui
RUN git clone https://github.com/SuperloreAI/stable-diffusion-webui.git && \
    cd stable-diffusion-webui && \
    git checkout 769def1e418c74107e4bfe1c7c990d20faed4c17

WORKDIR /app/stable-diffusion-webui

# SD Controlnet
RUN git clone https://github.com/SuperloreAI/sd-webui-controlnet.git extensions/sd-webui-controlnet && \
    cd extensions/sd-webui-controlnet && \
    git checkout 241c05f8c9d3c5abe637187e3c4bb46f17447029
    
RUN mkdir -p models/ControlNet
RUN mkdir -p models/openpose
RUN mkdir -p models/hed
RUN mkdir -p models/leres

RUN echo '{"control_net_model_cache_size": 10, "control_net_max_models_num": 6}' > config.json

# RUN git clone https://github.com/AUTOMATIC1111/stable-diffusion-webui.git && \
# cd stable-diffusion-webui && \
# git checkout 3e0f9a75438fa815429b5530261bcf7d80f3f101

ENV MODEL_URL=${MODEL_URL}
ENV CONTROLNET_MODEL_URLS=${CONTROLNET_MODEL_URLS}
ENV HF_TOKEN=${HF_TOKEN}
ENV OPENPOSE_MODEL_URLS=${OPENPOSE_MODEL_URLS}
ENV HED_URLS=${HED_URLS}
ENV DEPTH_LERES_MODEL_URLS=${DEPTH_LERES_MODEL_URLS}
ENV GCP_SERVICE_ACCOUNT_JSON=${GCP_SERVICE_ACCOUNT_JSON}

RUN pip install tqdm requests google-cloud-storage
ADD download_models.py .
RUN python download_models.py

ADD prepare.py .
RUN python prepare.py --skip-torch-cuda-test --xformers --reinstall-torch --reinstall-xformers

ADD download.py download.py
RUN python download.py --use-cpu=all

RUN mkdir -p extensions/banana/scripts
ADD script.py extensions/banana/scripts/banana.py
ADD app.py app.py
ADD server.py server.py

CMD ["python", "server.py", "--xformers", "--no-hashing", "--listen", "--port", "8000"]
