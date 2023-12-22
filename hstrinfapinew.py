# Import necessary libraries
import flask
from flask import Flask, request, render_template, jsonify
import numpy as np
import pandas as pd
from pathlib import Path
import torch
from torchvision import models
from torchvision import transforms
from torch.utils.data import Dataset
from torch.utils.data import DataLoader
from tqdm import tqdm
import sys
import os
import pma_python
from pma_python import core
from shapely.geometry import Point, MultiPoint
import json
import boto3
import os
from pathlib import Path

app = Flask(__name__)

# checkingforlevel
def find_level_x(pma_slide, sessionID, mgfnlevel):
    level_x = None
    closest_level_distance = float('inf')

    for i, magnification_level in enumerate(core.get_zoomlevels_list(pma_slide, sessionID=sessionID)):
        if core.get_magnification(pma_slide, i, True, sessionID) == mgfnlevel:
            level_x = i
            break
        else:
            # Calculate the distance to the current magnification level
            distance = abs(core.get_magnification(pma_slide, i, True, sessionID) - mgfnlevel)
            # Update closest_level_distance and level_x if this level is closer
            if distance < closest_level_distance:
                closest_level_distance = distance
                level_x = i

    return level_x
def ccrop(crop_size):
    transforms_ =  transforms.Compose([
            transforms.CenterCrop(crop_size),
            transforms.ToTensor()
    ])
    return transforms_

# creating data frame
def filtered_patches(pma_slide, stride, sessionID):
    h = core.get_slide_info(pma_slide, sessionID)["Width"]
    w = core.get_slide_info(pma_slide, sessionID)["Height"]
    stride = stride # input parameter
    thumb = np.array(core.get_thumbnail_image(pma_slide, h // stride, w // stride, sessionID=sessionID).convert('L'))
    arr = np.logical_and(thumb < 240, thumb > 20)
    df = pd.DataFrame(columns=['dim1', 'dim2'])
    df['dim1'], df['dim2'] = stride * np.where(arr)[1] + (stride // 2), stride * np.where(arr)[0] + (stride // 2)
    return df

def get_metadata(pma_slide, sessionID, mgfnlevel):
    level = find_level_x(pma_slide, sessionID, mgfnlevel)
    max_level_dim = core.get_pixel_dimensions(pma_slide, core.get_max_zoomlevel(pma_slide, sessionID), sessionID)[0]
    zoom_level_dim = core.get_pixel_dimensions(pma_slide, level, sessionID)[0]
    scale = zoom_level_dim / max_level_dim
    scale = scale * (mgfnlevel / core.get_magnification(pma_slide, level, exact=True, sessionID=sessionID))
    return scale
# dataset_pma_python
class WSIDataset(Dataset):
    def __init__(self, df, wsi, transform, scale, ps, sessionID):
        self.wsi = wsi
        self.transform = transform
        self.df = df
        self.scale = scale
        self.ps = ps
        self.sessionID = sessionID

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        x, y = self.df.iloc[idx, 0] - 512, self.df.iloc[idx, 1] - 512
        if x < 0: x = 0
        if y < 0: y = 0
        patch = core.get_region(self.wsi, x, y, width=self.ps, height=self.ps, scale=self.scale, sessionID=self.sessionID)
        patch = self.transform(patch.convert('RGB'))
        return patch
def sort_and_convert_to_multipoint(df, category):
    filtered_df = df[df['preds'] == category]
    sorted_df = filtered_df.sort_values(by='dim1')
    points = [Point(x, y) for x, y in zip(sorted_df['dim1'], sorted_df['dim2'])]
    multi_points = MultiPoint(points)
    wkt_str = multi_points.wkt
    return wkt_str



access_key_id = 'keyid'
secret_key = 'secretkey'
host = "hosturl"
s3 = boto3.client('s3',aws_access_key_id=access_key_id, aws_secret_access_key=secret_key, use_ssl=True, endpoint_url = host)

def csv_present(pma_slide,s3):
    key  =pma_slide.replace(".svs","_HISTOROI.csv")
    key = key.replace("CAIB_WSI/","")
    try:
        s3.head_object(Bucket='caib-wsi',Key = key)
        return 'file_present'
    except Exception as e:
        return 'file_not_present'


@app.route('/hstrinf')
def index():
    return render_template('index.html')


@app.route('/inference', methods=['POST', 'GET'])
def inference():
    if request.method == 'POST':
        #csv_dir = 'gen_csv'
        stride = 256
        ps = 1024
        bs = 256
        username = request.form.get('username')
        password = request.form.get('password')
        input_type = request.form.get('input_type')
        mgfnlevel = float(request.form.get('mgfnlevel'))

        sessionID = core.connect('urlhost', username, password)
        print(sessionID)

        if input_type == 'file':
            selected_files = [request.form.get('input_value')]
        elif input_type == 'directory':
            selected_directory = request.form.get('input_value')
            slides = core.get_slides(selected_directory, sessionID, recursive=True)
            selected_files = slides
        else:
            return "Invalid input type"

        for pma_slide in tqdm(selected_files):
            print(len(selected_files))
            y = csv_present(pma_slide,s3)
            if not '.svs' in pma_slide or y == 'file_present':
                print('Either the file is not svs or inference already ran')
                continue
            sessionID = core.connect('hosturl', username, password)
            device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

            model6 = models.resnet18().to(device)
            model6.fc = torch.nn.Linear(512, 6).to(device)
            model6.load_state_dict(torch.load('weights/model_6.pt', map_location=device))
            model6.eval()

            sm = torch.nn.Softmax(dim=1)

            w = core.get_slide_file_name(pma_slide)
            print(f'processing {w}...')
            #csv_path = Path(csv_dir) / f"{Path(w).stem}.csv"

            scale = get_metadata(pma_slide, sessionID, mgfnlevel)
            df = filtered_patches(pma_slide, stride, sessionID)
            print(f'batches = {1 + len(df) // bs}')
            base_transform = transforms.Compose([transforms.Resize(256), transforms.ToTensor()])
            ds = WSIDataset(df, pma_slide, base_transform, scale, ps, sessionID)
            dl = DataLoader(ds, batch_size=bs, shuffle=False, num_workers=4)
            probs = np.zeros((len(ds), 6))
            with torch.no_grad():
                for i, data in tqdm(enumerate(dl)):
                    out = model6(data.to(device))
                    probs[bs * i:bs * i + data.shape[0], :6] = sm(out).cpu().numpy()

            names = ['Epithelial', 'Stroma', 'Adipose', 'Artefact', 'Miscellaneous', 'Lymphocytes']
            maps = {idx: name for idx, name in enumerate(names)}
            df['preds'] = np.argmax(probs, axis=1)
            df['preds'] = df['preds'].map(maps)
            A = sort_and_convert_to_multipoint(df, 'Adipose')
            core.add_annotation(pma_slide, 'Adipose', 'Adipose', A, color='#008080', sessionID=sessionID)
            B = sort_and_convert_to_multipoint(df, 'Artefact')
            core.add_annotation(pma_slide, 'Artefact', 'Artefact', B, color='#A9A9A9', sessionID=sessionID)
            C = sort_and_convert_to_multipoint(df, 'Miscellaneous')
            core.add_annotation(pma_slide, 'Miscellaneous', 'Miscellaneous', C, color='#808000', sessionID=sessionID)
            D = sort_and_convert_to_multipoint(df, 'Lymphocytes')
            core.add_annotation(pma_slide, 'Lymphocytes', 'Lymphocytes', D, color='#000000', sessionID=sessionID)
            E = sort_and_convert_to_multipoint(df, 'Stroma')
            core.add_annotation(pma_slide, 'Stroma', 'Stroma', E, color='#FF0000', sessionID=sessionID)
            F = sort_and_convert_to_multipoint(df, 'Epithelial')
            core.add_annotation(pma_slide, 'Epithelial', 'Epithelial', F, color='#0000FF', sessionID=sessionID)

            csv = df.to_csv(index=False)
            key  =pma_slide.replace(".svs","_HISTOROI.csv")
            key = key.replace("CAIB_WSI/","")
            print(key)
            s3.put_object(Body = csv,Bucket = 'caib-wsi',Key = key)

            #continue
            

        sessionend = core.disconnect(sessionID)
       
        if sessionend:
            return "Inference ran successfully. Please check pma_studio for added annotations and visualizations."
           



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)
