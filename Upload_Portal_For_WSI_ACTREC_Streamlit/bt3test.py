import os
import streamlit as st
from pma_python import core
import numpy as np
from glob import glob
import sys
import time 
import cv2
import shutil
import datetime 
import streamlit as st
import pandas as pd
import boto3
import os
import time
import shutil
import tqdm
from tqdm import tqdm
from PIL import Image
import re

#image = Image.open('/drive4/Anshuman/testing_project/boto3uploadfiles/im.png')
st.image('/drive4/Anshuman/testing_project/boto3uploadfiles/im.png')

st.sidebar.image("/drive4/Anshuman/testing_project/boto3uploadfiles/Logo_r.png", use_column_width=True)


access_key_id = 'caib-pathadmin'
secret_key = 'DI2WC8g/ttSFf+02KN1ADtbeX0PX9fJaCzjJdsqN'
host = "http://10.100.76.46:9020"
s3 = boto3.client('s3', aws_access_key_id=access_key_id, aws_secret_access_key=secret_key, use_ssl=True, endpoint_url=host)



def log_file_upload(file_name,selected_target_folder,remarks,y1):
    current_time = datetime.datetime.now()
    log_entry = [current_time,filename,selected_target_folder,y1]
    log_file = 'file_upload_log.csv'
    with open (log_file, mode = 'a',newline = '') as file:
         writer = csv.writer(file)
         if not log_file_exists:
            writer.writerrow(["Timestamp','File_Name',Target_Folder','Remarks','finger_print'])
            writer.writerow(log_entry)
      return log_entry

def file_present_in_bucket(s3,filename,selected_target_folder):
    paginator = s3.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=selected_target_folder)
    for page in pages:
        if not 'Contents' in page.keys():
            continue
        for obj in page['Contents']:
            if filename in obj['Key']:
                return True
    return False


# list files in a folder
def list_files_in_folder(folder_path):
    try:
        files = os.listdir(folder_path)
        return files
    except Exception as e:
        return []


        
def upload_file_to_caibwsi(s3,f,sufix,file_local,selected_target_folder):
    if file_present_in_bucket(s3,f,selected_target_folder):
        f_= f
        f2 = os.path.normpath('CAIB' + '/' + f_[:16] + '/' + f_[:21] + '/' + f_[:-4] + '/' + f)
        while file_present_in_bucket(s3, f, selected_target_folder):
            f = f_[:-4] + '_' + str(sufix) + f_[-4:]
            sufix += 1
        file_s3 = os.path.normpath('CAIB' + '/' + f_[:16] + '/' + f_[:21] + '/' + f_[:-4] + '/' + f)
        y = st.write('File_already_exists_Uploading:', file_local, "with_target_structure:",file_s3)
    else:
        f_ = f
        file_s3 = os.path.normpath('CAIB' + '/' + f_[:16] + '/' + f_[:21] + '/' + f_[:-4] + '/' + f)
        y = st.write("File_does_not_exist_uploading:", file_local, "with_target_structure:", file_s3)

    return file_s3,y,f2


    
def upload_file_to_tmc_diagnostic(s3,f,sufix,file_local,selected_target_folder):
    f = f
    #pfx, sufx = f.split('W', 1)
    #pfx += 'W'
    m = re.search(r'[a-zA-Z]{2}',f)
    pfx,sufx = fr[:m.start()+2],fr[m.start()+2:]
    fdi = sufx.find('-')
    if fdi ==0:
        sufx = '_'+sufx[fdi+1:]
    else:
        if fdi < 0:
            sufx = sufx
    f = pfx + sufx
   
    if file_present_in_bucket(s3,f,selected_target_folder):
        f_ = f
        
        while file_present_in_bucket(s3,f,selected_target_folder):
            f = f_.replace('.svs','^'+str(sufix)+'.svs')
            sufix += 1
        file_s3 = f[:8] +'/'+ f
        y = st.write('File_already_exists_Uploading:', file_local, "with_target_structure:",file_s3)
    else:
        f = f
        f2 = 'NA'
        m = re.search(r'[a-zA-Z]{2}',f)
        pfx,sufx = fr[:m.start()+2],fr[m.start()+2:]
        pfx = ''.join(c if c.isalnum() else '' for c in pfx)
        fdi = sufx.find('-')
        if fdi ==0:
            sufx = '_'+sufx[fdi+1:]
        else:
            if fdi < 0:
                sufx = sufx
        if len(pfx) < 8:
            pfx = '00' + pfx
            file_s3 = pfx + '/' + pfx +sufx
            y = st.write("File_does_not_exist_uploading:", file_local, "with_target_structure:", file_s3)
        else:
            file_s3 = pfx + '/' + pfx + sufx
            y = st.write("File_does_not_exist_uploading:", file_local, "with_target_structure:", file_s3)
            
    return file_s3,y,f2
        




        


        
# Streamlit app
def main():
    st.title('Scanned Files Uploading API')

    # Root directory
    mount_point = '/run/user/1000/gvfs/smb-share:server=10.100.1.80,share=d'
    root_directory = os.path.join(mount_point, 'Final_Images')

    # list of folders in the root directory
    folders = [f for f in os.listdir(root_directory) if os.path.isdir(os.path.join(root_directory, f))]

    # Adding sidebar to multi-select folders
    selected_folders = st.sidebar.multiselect("Select Local Folder",folders)

    # Using the sidebar to multi-select files within the selected folders
    #selected_files = []
    #for folder in selected_folders:
        #folder_path = os.path.join(root_directory, folder)
        #files = list_files_in_folder(folder_path)
        #selected = st.sidebar.multiselect(f'Select Files in {folder}:', files)
        #selected_files.extend([os.path.join(folder,file) for file in selected])
        
    #  sidebar to multi-select files within the selected folders
    selected_files = []
    select_all = False
    for folder in selected_folders:
        folder_path = os.path.join(root_directory, folder)
        files = list_files_in_folder(folder_path)
        select_all = st.sidebar.checkbox(f'Select All Files in {folder}')
        if select_all:
            selected_files.extend([os.path.join(folder, file) for file in files])
        else:
            selected = st.sidebar.multiselect(f'Select Individual Files in {folder}:', files)
            selected_files.extend([os.path.join(folder, file) for file in selected])


    # Display selected files
    st.write(len(selected_files),'Files Selected:')
    for file in selected_files:
        st.write(f'- {file}')

    target_folders = ["select_folder","caib-research", "caib-wsi","tmc-diagnostics"]#for any other folder where no caib files are there we need to change logic for other files for structure.


    selected_target_folder = st.selectbox("Select Target Folder", target_folders)


    sufix = 2
    # Upload button
    if st.button('Upload Selected Files'):
        st.write('uploading',len(selected_files),'files.....')
        #for file_id in selected_files:
        for i in tqdm(selected_files,desc ="uploaing_wsi",dynamic_ncols=True):
            slide_id = i.split('/')[-1]
            file_local = os.path.join(root_directory,i)
            
        
           
            
            #sufix = 2
            f = slide_id
            st.write('slide_id:',f)
            st.write('slide_path:',file_local)
            
            
            if selected_target_folder == "caib-wsi":
                file_s3,y,f2 = upload_file_to_caibwsi(s3=s3,f=slide_id,sufix = sufix,file_local=file_local,selected_target_folder="caib-wsi")
                print(y)
            else:
                file_s3,y,f2 = upload_file_to_tmc_diagnostic(s3=s3,f=slide_id,sufix=sufix,file_local=file_local,selected_target_folder = "tmc-diagnostics")
                print(y)
                
                
            t = datetime.datetime.strptime(time.ctime(os.path.getctime(file_local)), "%a %b %d %H:%M:%S %Y")
            st.write('image_scanned_on',t)
            srt=time.time()
            st.write('uploading....')
            s3.upload_file(file_local,selected_target_folder, file_s3)
            et=time.time()
            st.write("time for upload:",et-srt)
            st.write('Upload complete!','Successfuly added to',selected_target_folder)
            #if selected_target_folder == 'tmc_diagnostic':
                #file_s4 = 'TMC_diagnostic_actrec'+'/'+file_s3
                #y1 = core.get_fingerprint(file_s4,sessionID=core.connect('https://caib-pma.actrec.gov.in/core/','tmccomputpath','Z5XPLQ2I'))
                #st.write('finger_print_generated as',y1,'. Removing file from local folder permanently')
                #y2 = core.get_fingerprint(f2,sessionID=core,connect('https://caib-pma.actrec.gov.in/core/','tmccomputpath','Z5XPLQ2I'))
                #st.write('finger print of file with same name earlier',y2)
                #remarks = 
                #log_entry = log_file_upload()
                #st.write('Log Entry',log_entry)
                #if y1 == y2 :
                    #print('file with same finger print exist, deleting the latest uploaded file from local and bucket')
                    #s3.delete_object(Bucket=selected_target_folder, Key= file_s3)
                    #os.remove(file_local)
                    #remarks = 
                    #log_entry = log_file_upload()
                    #st.write('Log Entry',log_entry)
                #else:
                    #os.remove(file_local)
                    #remarks = 
                    #log_entry = log_file_upload()
                    #st.write('Log Entry',log_entry)
            #else:
                #if selected_targeted_folder == 'caib_wsi':
                    #y1 = core.get_fingerprint(file_s3,sessionID=core.connect('https://caib-pma.actrec.gov.in/core/','tmccomputpath','Z5XPLQ2I'))
                    #st.write('finger_print_generated as',y1)
                    #y2 = core.get_fingerprint(f2,sessionID=core.connect('https://caib-pma.actrec.gov.in/core/','tmccomputpath','Z5XPLQ2I'))
                    #st.write('finger print of file with same name earlier',y2)
                    #remarks = 
                    #log_entry = log_file_upload()
                    #st.write('Log Entry',log_entry)
                    #if y1 == y2:
                        #print('file with same finger print exist, uploading the latest uploaded file to back_up bucket')
                        #s3.upload_file(file_local,'caib_backup',f2)
                        #s3.delete_object(Bucket=selected_target_folder, Key= file_s3)
                        #os.remove(file_local)
                        #remarks = 
                        #log_entry = log_file_upload()
                        #st.write('Log Entry',log_entry)
                   #else: 
                        #s3.upload_file(file_local,'caib_backup',f2)
                        #os.remove(file_local)
                        #remarks = 
                        #log_entry = log_file_upload()
                        #st.write('Log Entry',log_entry)
                        
                    
            continue
            

if __name__ == '__main__':
    main()
