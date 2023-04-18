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
    https://huggingface.co/lllyasviel/ControlNet/blob/main/models/control_sd15_normal.pth,\
    https://huggingface.co/CiaraRowles/TemporalNet/blob/main/diff_control_sd15_temporalnet_fp16.safetensors"

ARG OPENPOSE_MODEL_URLS="\
    https://huggingface.co/lllyasviel/ControlNet/resolve/main/annotator/ckpts/hand_pose_model.pth,\
    https://huggingface.co/lllyasviel/ControlNet/resolve/main/annotator/ckpts/body_pose_model.pth"

ARG HED_URLS="\
    https://huggingface.co/lllyasviel/ControlNet/resolve/main/annotator/ckpts/network-bsds500.pth"

ARG DEPTH_LERES_MODEL_URLS="\
    https://cloudstor.aarnet.edu.au/plus/s/lTIJF4vrvHCAI31/download"

# If you are using a private Huggingface model (sign in required to download) insert your Huggingface
# access token (https://huggingface.co/settings/tokens) below:
ARG HF_TOKEN='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'

ARG GCP_SERVICE_ACCOUNT_JSON='{"type": "service_account", "project_id": "superlore-demo", "private_key_id": "892e164b068652a2587cfeb6a2a08a2b5877f50a", "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC5vMw9rwGQTl3i\nSXJbuXEOWv/Zk88SCnkuXmSNNynZl9ncrg0RBEZHglo5S0LryUbZ0Y7APcwXQBWX\nvGSTY1deDlqyY9dvRPe51sEvuGmbHiVB00FltwSbwRIuI8t2PLHOIcayX/Kgfi5z\nUavosWE5xbp0HzNSlbVUaczmpYYbFrsRmgl3A41M+bFtbgybjXzlb7+QCNWdrfyW\n0Ucg6Q74Ao6k2Vs1F161N5i5L2x3UXvwyCZeedwChrZwVAMBCnVoX8oc4rGFo+MY\nKRjcLK7lHUw0ZH3m/iMaSN+t3sjHUkOoVdBw4XtN5S1Ua7FNRcZLRDa3pZASixYi\nQiiWs5EXAgMBAAECggEACXdBwXMF1WDpD/tGRL5ysJSarXAHAZhfDKnq3feNvnUq\nuUB1kgRxwHs4NetMAdBEOB2h9NIxcI3ni9AiIBDUBwscPDMya41MQsBbIB954lnq\n9CvcDV8CcR2p24gfemsldKfsBHM3Xk6P93iWFknT9qnJEtn0N6VBlIe/1ZFiAEdV\n3O3nyoEKIl/4ifCGagm4RyGwyeyGlM70m7k3BOAFFCO/YR2rxnnQyHJ885WlBDsq\nM2cYJr/9AdQgwgDPxQWNy0OSwe1lD8lgTteQhDS693uHnTZc9qp7gLAclY2DAfHS\nk/XvTlR5VM8yykXBsxfZtEuGJZxNbQtwo6/TR1BTgQKBgQD5GdpHxX9RMIyidGMl\nvbjDklUfFc0nPxLF7lqu3cven0hlo2l9rfCywo6dDWUbBlHxlXRX//jgbjKPURZ3\nLW7SHpIOOZPHaJyFDGotnjE/oVwpT2lLf+DP+dVnKTRplka5lCI1vRIXiaLnE35+\n3zIv9bZbBfiVcSKFgW+w1RAa8QKBgQC+4bFKtNNJCFYl0gZGobrLCplA2hgUDdsu\ne0FYVPg/qejMWadKDGT3Md9yxkOuMYVVHtSbVZokN1iNqk9/uqxIyFG3yYsVQGfv\nWe9op1o7veQoDK+cGKu4q6vJBeJvLP7t47i4HUr4XOYFwfUrnrR79OKYdu4Mnam9\nJnVYPnMchwKBgQDGwvcmD5Ogb/G3atD1+2VjP+8Fx7qT10Mehir7nuSedVAqMXLq\nIpGNwapT7K1BHBDkiFF2KjwmsCdNrfEUFT95D4WRLiYZlgJWM2rBjZlUYWeNWtz0\nrkvvBzVdhEZa/drfFzEY2g2GlH9UjHyBtYxxMklYZfJNJCHcj0RUwB2CsQKBgA8p\nsoGyt433oZBDjMgTlNkIMIBcUslVCHI6zEgOB+JWxu1kuctCDMsuJQfjBAFUYbkP\nR+hG9oWl99zZCJOm6oSllQg6dFft09PJmyD/GkXgob0ktNZ7hziWOoEvfHtEYcPX\n8RZ/DTOJfaQ7chRS+RdXrqBZ4jMSWydxZKTr4Q0FAoGAe1KMroRhiHNeYtIMZwPP\ny0lgdJuxQzFN3B9qdR9HK/4+LM9pSvj9QTgBdsZaEBLUSiqUTToCrWfNVZmtCkdP\nwtLHgLLoCq0p1/SZgj3dAURl8T1Zww55LIKt7J2E+htNOReWQNJMqmoY3tY3WMcs\n9FbvqUm2K8cVr5O6bAldZKc=\n-----END PRIVATE KEY-----\n", "client_email": "inference-machines@superlore-demo.iam.gserviceaccount.com", "client_id": "101934595030530880425", "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token", "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs", "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/inference-machines%40superlore-demo.iam.gserviceaccount.com"}'

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
