import numpy as np
import torch
import torch.nn as nn
import serial
import time

class emg_cnn(nn.Module):
  def __init__(self):
    super().__init__()

    self.conv1 = nn.Conv1d(4,16,kernel_size=3)
    self.pool = nn.MaxPool1d(2)
    self.conv2 = nn.Conv1d(16,32,kernel_size=3)

    self.fc1 = nn.Linear(416, 64)
    self.fc2 = nn.Linear(64,3)

    self.bn1= nn.BatchNorm1d(16)
    self.bn2 = nn.BatchNorm1d(32)

  def forward(self, x):
    x = self.pool(torch.relu(self.bn1(self.conv1(x))))
    x = self.pool(torch.relu(self.bn2(self.conv2(x))))

    x = x.view(x.size(0),-1)

    x = torch.relu(self.fc1(x))
    x = self.fc2(x)

    return x


model = emg_cnn()
model.load_state_dict(torch.load("emg_CNN.pth", map_location="cpu"))
model.eval()

mean = np.load("emg_mean.npy")
std = np.load("emg_std.npy")

buffer = []
history=[]
last_sent=0

port = "COM6"
baud = 115200
window = 60
esp_port = "COM3"

ser = serial.Serial(port, baud)
#esp = serial.Serial(esp_port,baud)

#time.sleep(2)

while True:
  try:
    line = ser.readline().decode().strip()
    parts = line.split(",")
    if len(parts) < 2:
      continue

    try:
      ch0=float(parts[0])
      ch1=float(parts[1])

    except ValueError:
      continue


    sample = [ch0,ch1]
    buffer.append(sample)

    if len(buffer)>window:
      buffer.pop(0)

    if len(buffer)==window:
      data = np.array(buffer).T

      data = data - np.mean(data,axis=1,keepdims=True)
      data = data/512.0
      data = data*450

      rms = np.sqrt(np.mean(data**2,axis=1,keepdims=True))
      rms= np.repeat(rms,window,axis=1)

      data = np.concatenate([data,rms], axis=0)
      tensor = torch.tensor(data,dtype=torch.float32).unsqueeze(0)

      tensor = (tensor - torch.tensor(mean, dtype=torch.float32)) / torch.tensor(std, dtype=torch.float32)

      with torch.no_grad():
        output = model(tensor)
        gesture = torch.argmax(output,dim=1).item()

        history.append(gesture)
        if len(history)>3:
          history.pop(0)

        stable_g = max(set(history), key=history.count)
        if stable_g != last_sent:
          print("Sending gesture:", stable_g)
          #esp.write(f"{stable_g}\n".encode())
          last_sent = stable_g
          #time.sleep(0.05)


        #print("Predicted gesture", stable_g)
        #print(data)
  except KeyboardInterrupt:
    break

ser.close()
#esp.close()

