import numpy as np
import pandas as pd
from flask import Flask, render_template, request, flash
import boto3
import botocore
from tqdm import tqdm
from pathlib import Path
from datetime import datetime
import pma_python
from pma_python import core


app = Flask(__name__)
app.secret_key = 'b2bsync1234'




def list_files(bucket_name, s3):
    file_list = []
    bucket_objects = s3.list_objects_v2(Bucket=bucket_name)
    for obj in bucket_objects.get("Contents", []):
        file_list.append(obj["Key"])
    return file_list

def file_present_in_bucket(s3, filename):
    paginator = s3.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket='caib-wsi')
    for page in pages:
        if not 'Contents' in page.keys():
            continue
        for obj in page['Contents']:
            if filename in obj['Key']:
                return True
    return False


def copy_files(source_bucket, selected_files, source_bucket_objects, s3):
    try:
        with tqdm(total=len(selected_files), desc="Copying files") as pbar:
            for key in selected_files:
                fp_bucket = source_bucket.replace("-","_")
                fpkey = str(Path(fp_bucket) / key)

                try:
                    sessionID=core.connect('urlhost/','username','password')
                    y = core.get_fingerprint(fpkey, sessionID)
                except Exception as e:
                    flash(f"Error getting fingerprint for file '{key}': {e}")
                    # Create a new key and upload to 'no_finger_print_folder'
                    time_now = datetime.today().strftime('%d-%m-%Y:%H:%M:%S')
                    parts = key.split('CAIB')
                    newkey = f'{parts[0]}{Path(key).stem}_{time_now}{Path(key).suffix}'
                    part = newkey.split('/')
                    new_key_copy = f'{part[0]}/transfer_failed/{"/".join(part[1:])}'
                    s3.copy_object(CopySource={'Bucket': source_bucket, 'Key': key}, Bucket=source_bucket, Key=new_key_copy)
                    flash(f"File '{key}' does not have a fingerprint.")
                    #s3.delete_object(Bucket=source_bucket, Key=key)
                    flash(f"Old file structure '{key}' replaced in the source bucket with {new_key_copy}.")

                    pbar.update(1)
                    continue  # Skip to the next iteration

                # The fingerprint exists, continue processing the file
                if "successfully_processed" in key or "transfer_failed" in key:
                    flash("file is processed for transfer already")
                    pbar.update(1)
                    continue

                else:
                    new_key_dest = f'CAIB/{Path(key).stem[:16]}/{Path(key).stem[:21]}/{Path(key).stem}{Path(key).suffix}'
                    if file_present_in_bucket(s3, new_key_dest):
                        flash(f"File '{new_key_dest}' already exists in the destination bucket. Skipping the copying.")
                    else:
                        flash(f"File '{new_key_dest}' does not exist already. Copying to caib-wsi.")
                        s3.copy_object(CopySource={'Bucket': source_bucket, 'Key': key}, Bucket='caib-wsi', Key=new_key_dest)
                        time_now = datetime.today().strftime('%d-%m-%Y:%H:%M:%S')
                        parts = key.split('CAIB')
                        newkey = f'{parts[0]}{Path(key).stem}_{time_now}{Path(key).suffix}'
                        part = newkey.split('/')
                        new_key_copy = f'{part[0]}/successfully_processed/{"/".join(part[1:])}'
                        s3.copy_object(CopySource={'Bucket': source_bucket, 'Key': key}, Bucket=source_bucket, Key=new_key_copy)
                        flash(f"File '{key}' copied to '{new_key_copy}' in the source bucket.")
                        s3.delete_object(Bucket=source_bucket, Key=key)
                        flash(f"Old file structure '{key}' replaced in the source bucket with {new_key_copy}.")

                        pbar.update(1)
    except botocore.exceptions.ClientError as e:
        return False
    return True



# Initialize the S3 client
access_key_id = 'acceskeyid'
secret_key = 'secretkey'
host = "hosturl"
s3 = boto3.client('s3', aws_access_key_id=access_key_id, aws_secret_access_key=secret_key, use_ssl=True, endpoint_url=host)

sessionID=core.connect('urlhost','username','password')


@app.route('/b2bsync', methods=['GET', 'POST'])
def index():
    if request.method == "POST":
        source_bucket = request.form.get('source_bucket')

        source_bucket_objects = list_files(source_bucket, s3)
        selected_files = source_bucket_objects  # to copy all files
        destination_bucket = 'caib-wsi'  # Replace with the actual destination bucket
        if copy_files(source_bucket, selected_files, source_bucket_objects, s3):
            flash(f"File synchronization for {source_bucket} complete. Files synced successfully")
        else:
            flash(f"Error during file synchronization for {source_bucket}. Please retry.")
    return render_template('index.html')



if __name__ == "__main__":
    app.run(host = '0.0.0.0',port= 5000,debug=True)
