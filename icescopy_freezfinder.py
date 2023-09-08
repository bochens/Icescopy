from PySide6.QtWidgets import (QPushButton, QFileDialog, QVBoxLayout, QLineEdit, QLabel,
                              QSizePolicy, QHBoxLayout,QDialog, QSpacerItem, QFrame, QRadioButton)
from PySide6.QtGui import Qt
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import signal
import re

class FreezeFinderDialog(QDialog):
    def __init__(self):
        super(FreezeFinderDialog, self).__init__()

        self.setWindowTitle('Convolution freeze finder script')
        self.setGeometry(100, 100, 400, 300)

        layout = QVBoxLayout()

        # Set a fixed height
        self.setFixedHeight(350)

        # Set the vertical size policy to fixed
        sizePolicy = self.sizePolicy()
        sizePolicy.setVerticalPolicy(QSizePolicy.Fixed)
        self.setSizePolicy(sizePolicy)

        # Input File 1 Image grayscale file
        file1_layout = QHBoxLayout()
        self.input_file1_edit = QLineEdit()
        self.input_file1_button = QPushButton('Select')
        self.input_file1_button.clicked.connect(self.select_input_file1)
        file1_layout.addWidget(QLabel('Image grayscale file*:'))
        file1_layout.addWidget(self.input_file1_edit)
        file1_layout.addWidget(self.input_file1_button)
        layout.addLayout(file1_layout)
        self.input_file1_button.setFocusPolicy(Qt.NoFocus)

        # Input File 2 Linkam data file
        file2_layout = QHBoxLayout()
        self.input_file2_edit = QLineEdit()
        self.input_file2_button = QPushButton('Select')
        self.input_file2_button.clicked.connect(self.select_input_file2)
        file2_layout.addWidget(QLabel('Linkam data file*:'))
        file2_layout.addWidget(self.input_file2_edit)
        file2_layout.addWidget(self.input_file2_button)
        layout.addLayout(file2_layout)
        self.input_file2_button.setFocusPolicy(Qt.NoFocus)

        # Input File 3
        file3_layout = QHBoxLayout()
        self.input_file3_edit = QLineEdit()
        self.input_file3_button = QPushButton('Select')
        self.input_file3_button.clicked.connect(self.select_input_file3)
        file3_layout.addWidget(QLabel('Temperature correction file:'))
        file3_layout.addWidget(self.input_file3_edit)
        file3_layout.addWidget(self.input_file3_button)
        layout.addLayout(file3_layout)
        self.input_file3_button.setFocusPolicy(Qt.NoFocus)

        # Output File
        file_output_layout = QHBoxLayout()
        self.output_file_edit = QLineEdit()
        self.output_file_button = QPushButton('Select')
        self.output_file_button.clicked.connect(self.select_output_file)
        file_output_layout.addWidget(QLabel('Output File*:'))
        file_output_layout.addWidget(self.output_file_edit)
        file_output_layout.addWidget(self.output_file_button)
        layout.addLayout(file_output_layout)
        self.output_file_button.setFocusPolicy(Qt.NoFocus)

         # --- Spacer and Separator Line between Output File and Other Inputs ---
        layout.addItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))
        hline2 = QFrame()
        hline2.setFrameShape(QFrame.HLine)
        hline2.setFrameShadow(QFrame.Sunken)
        layout.addWidget(hline2)

        # Additional Input Boxes for Width and Prominence
        additional_inputs_layout = QHBoxLayout()

        # Width Input
        self.width_edit = QLineEdit()
        additional_inputs_layout.addWidget(QLabel('Peak finding width:'))
        additional_inputs_layout.addWidget(self.width_edit)
        self.width_edit.setText("10")

        # Prominence Input
        self.prominence_edit = QLineEdit()
        additional_inputs_layout.addWidget(QLabel('Peak finding Prominence:'))
        additional_inputs_layout.addWidget(self.prominence_edit)
        self.prominence_edit.setText("100")

        layout.addLayout(additional_inputs_layout)

        # OK and Cancel buttons
        self.ok_button = QPushButton('OK')
        self.ok_button.clicked.connect(self.run_freeze_finder_script)

        self.cancel_button = QPushButton('Cancel')
        self.cancel_button.clicked.connect(self.reject)

        layout.addWidget(self.ok_button)
        layout.addWidget(self.cancel_button)

        self.setLayout(layout)
        

    def select_input_file1(self):
        file_name, _ = QFileDialog.getOpenFileName(self, 'Select image grayscale file')
        if file_name:
            self.input_file1_edit.setText(file_name)

    def select_input_file2(self):
        file_name, _ = QFileDialog.getOpenFileName(self, 'Select Linkam data file')
        if file_name:
            self.input_file2_edit.setText(file_name)
    
    def select_input_file3(self):
        file_name, _ = QFileDialog.getOpenFileName(self, 'Select temperature correction file')
        if file_name:
            self.input_file3_edit.setText(file_name)

    def select_output_file(self):
        file_name = QFileDialog.getExistingDirectory(self, 'Select Output Path')
        if file_name:
            self.output_file_edit.setText(file_name)

    def run_freeze_finder_script(self):

        try:

            gsm_file_path           = self.input_file1_edit.text()
            linkam_file_path        = self.input_file2_edit.text()
            correction_file_path    = self.input_file3_edit.text()
            output_dir              = self.output_file_edit.text()
            width                   = float(self.width_edit.text())
            prominence              = float(self.prominence_edit.text())

            str_array = np.loadtxt(gsm_file_path, delimiter = ",", dtype=str, skiprows=2)

            # read grayscale mean file
            filename_array = str_array[:, 0]
            datetime_array = str_array[:, 1]
            flag_array     = str_array[:, 2]=='flagged'
            circle_data = str_array[:, 3:].astype(float)
            image_grayscale_data = circle_data[:, ::4]

            # read the time from grayscale:
            if datetime_array[0] == 'None':
                datetime_strs = [fname.split('-')[0] + '-' + fname.split('-')[1] + '-' + fname.split('-')[2] + 'T' + 
                            fname.split('-')[3] + ':' + fname.split('-')[4] + ':' + fname.split('-')[5]
                            for fname in filename_array]

                image_datetime_array = np.array(datetime_strs, dtype='datetime64[us]')
            else:
                image_datetime_array = np.array(datetime_array, dtype='datetime64[us]')


            # Read Excel file
            df = pd.read_excel(linkam_file_path)
            linkam_headers = df[:104].to_numpy()[:,0]

            LDF_file_string = linkam_headers[1]
            match = re.search(r'(\d{2}-\d{2}-\d{2} \d{2}-\d{2}-\d{2}-\d{2})', LDF_file_string)
            date_str = match.group(1)
            formatted_date_str = '20' + date_str[6:8] + '-' + date_str[3:5] + '-' + date_str[:2] + 'T' + date_str[9:11] + ':' + date_str[12:14] + ':' + date_str[15:17] + '.' + date_str[18:]

            first_datetime = np.datetime64(formatted_date_str, 'us')

            sample_period = float(re.search(r'([\d.]+)', linkam_headers[6]).group(1)) # in seconds

            linkam_temperature_ramp = linkam_headers = df[104:].to_numpy()[:,2].astype('float')
            linkam_indexes = np.arange(len(linkam_temperature_ramp))
            linkam_time_passed = linkam_indexes * np.timedelta64(int(sample_period*1E6), 'us')
            linkam_time_array = first_datetime + linkam_time_passed

            linkam_time_stamps = linkam_time_array.astype('datetime64[ms]').astype('int')
            image_time_stamps = image_datetime_array.astype('datetime64[ms]').astype('int')

            interpolated_image_temps = np.interp(image_time_stamps, linkam_time_stamps, linkam_temperature_ramp, left = np.nan, right = np.nan)

            # Read temperature correction file
            if correction_file_path: # if user input the correction_file_path
                correction_data = np.loadtxt(correction_file_path, delimiter = ",", skiprows=1)

                well_num = correction_data[:,0]
                slope_val = correction_data[:,1]
                intercept_val = correction_data[:,2]

                def correct_for_actural_temp(measured_temp, the_well_num):
                    the_slope_val = slope_val[the_well_num]
                    the_intercept_val = intercept_val[the_well_num]

                    return (measured_temp - the_intercept_val)/the_slope_val

            with open(os.path.join(output_dir, "freezing_output.csv"), 'w') as the_file:
                the_file.write('image_index,image_name,date_time,raw_temperature,corrected_temperature\n')

            for j in np.arange(image_grayscale_data.shape[1]):
                with open(os.path.join(output_dir, "freezing_output.csv"), 'a') as the_file:
                    the_file.write('selection_'+str(j))
                    the_file.write("\n")
                
                g_data = image_grayscale_data[:, j]

                g_daray = np.array(g_data) - np.average(g_data)

                step = np.hstack((np.ones(len(g_daray)), -1*np.ones(len(g_daray))))
                g_daray_step = np.convolve(g_daray, step, mode='valid')

                peaks = signal.find_peaks(-g_daray_step, width=width, prominence=prominence)[0]

                fig1 = plt.figure(figsize=[10, 5])

                plt.plot(np.arange(len(g_daray)), g_daray*100)
                plt.plot(np.arange(len(g_daray_step)), g_daray_step)
                plt.title('selection '+str(j))
                plt.xlabel('image number')
                
                with open(os.path.join(output_dir, "freezing_output.csv"), 'a') as the_file:
                    for i in range(len(peaks)):
                        plt.axvline(x = peaks[i], color='r')
                        the_file.write(str(peaks[i]))
                        the_file.write(",")
                        the_file.write(str(filename_array[peaks[i]]))
                        the_file.write(",")
                        the_file.write(str(image_datetime_array[peaks[i]]))
                        the_file.write(",")
                        the_file.write("{:.3f}".format(interpolated_image_temps[peaks[i]]))
                        the_file.write(",")
                        if correction_file_path:
                            the_file.write("{:.3f}".format(correct_for_actural_temp(interpolated_image_temps[peaks[i]], j)))
                        else:
                            the_file.write("nan")
                        the_file.write("\n")

                plt.savefig(os.path.join(output_dir, str(j)+".png"), dpi=300)

            fig2 = plt.figure(figsize=(12, 6))
            plt.subplot(1, 1, 1)
            plt.plot(linkam_time_array, linkam_temperature_ramp, 'b', label='Linkam Temperature Ramp')

            # Plot interpolated image temperatures
            plt.plot(image_datetime_array, interpolated_image_temps, 'r', label='Interpolated Image Temperatures')

            plt.xlabel('Datetime')
            plt.ylabel('Temperature (Celsius)')
            plt.legend()
            plt.title('Linkam Temperature')
            plt.grid(True)

            plt.savefig(os.path.join(output_dir,"temperature_ramp.png"), dpi=300)

        except Exception as err:
            print(err)
            self.reject()
        else:
            self.accept()

        