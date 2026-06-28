import numpy as np
import pandas as pd
from scipy.io import loadmat
import glob

from google.colab import drive
drive.mount('/content/drive')

subjects = range(1,16)
for s in subjects:
  path = f"/content/drive/MyDrive/Prosthetic_Hand/Raw_Data/S{s}_A1_E3.mat"
  mat = loadmat(path)

  demg = mat['emg']
  dlabels = mat['restimulus']

  print(demg.shape)
  print(dlabels.shape)
  dlabels = dlabels.flatten()

  mask = np.isin(dlabels, [0,2,14])
  emg = demg[mask]
  labels = dlabels[mask]
  print(emg.shape)
  print(np.unique(labels))

  df = pd.DataFrame(emg)
  df['class'] = labels
  df['subject'] = s

  save_path = f"/content/drive/MyDrive/Prosthetic_Hand/Data/S{s}.csv"
  df.to_csv(save_path, index = False)

files = glob.glob("/content/drive/MyDrive/Prosthetic_Hand/Data/S*.csv")

dfs = [pd.read_csv(f) for f in files]
df = pd.concat(dfs, ignore_index=True)
#print(df.shape)
#print(df["class"].unique())

sel_channel = [0,6]

signals = df.iloc[:, sel_channel].values
labels = df["class"].values
subjects = df["subject"].values

#print(signals.shape)
#print(labels.shape)

classes = np.unique(labels)
class_map = {cls: i for i,cls in enumerate(classes)}
labels = np.array([class_map[x] for x in labels])

print(np.unique(labels))

channels = signals.shape[1]
for ch in range(channels):
  print("channel :", ch)
  rms_val =[]

  for cls in np.unique(labels):
    cls_data = signals[labels==cls, ch]
    rms = np.sqrt(np.mean(cls_data**2))
    rms_val.append(rms)
    print("class: ", cls, " rms: ", rms)

  sep=max(rms_val) - min(rms_val)
  print("rms_spread: ", sep)

signal_norm = np.zeros_like(signals)

for i in np.unique(subjects):
  mask = subjects == i
  subj_data = signals[mask]

  mean = subj_data.mean(axis=0, keepdims = True)
  std = subj_data.std(axis=0, keepdims = True)

  signal_norm[mask] = (subj_data-mean)/std

def window_dat(signal_norm, labels, subjects, size, stride):
  x=[]
  y=[]
  subj = []

  for s in np.unique(subjects):
    s_mask = subjects == s
    s_sig = signal_norm[s_mask]
    s_lab = labels[s_mask]

    for cls in np.unique(s_lab):
      class_data = s_sig[s_lab == cls]

      for i in range(0, len(class_data)-size, stride):
        window = class_data[i:i+size]
        x.append(window.T)
        y.append(cls)
        subj.append(s)

  return np.array(x), np.array(y), np.array(subj)

window_size = 60  #ninapro db sampling freq = 100Hz, for 200ms we have 20 samples
stride_length = 15
x,y,subj = window_dat(signal_norm, labels, subjects, window_size,stride_length)

print(x.shape)

class_0 = np.where(y==0)[0]
class_1 = np.where(y==1)[0]
class_2 = np.where(y==2)[0]
samples_per_class = 5579

np.random.seed(42)

samples_0 = np.random.choice(class_0, samples_per_class, replace="False")
samples_1 = np.random.choice(class_1, samples_per_class, replace="False")
samples_2 = np.random.choice(class_2, samples_per_class, replace="False")

equal_data = np.concatenate([samples_0, samples_1, samples_2])
np.random.shuffle(equal_data)

x_data = x[equal_data]
y_data = y[equal_data]

for cls in np.unique(y_data):
  print(cls, np.sum(y_data==cls))

print(x_data.shape)

rms = np.sqrt(np.mean(x_data**2, axis=2, keepdims=True))
rms = np.repeat(rms,x_data.shape[2], axis=2)
print(rms.shape)

x_data = np.concatenate([x_data, rms], axis=1)
print(x_data.shape)

mean = x_data.mean(axis=(0,2), keepdims=True)
std = x_data.std(axis=(0,2), keepdims=True)

x_data = (x_data - mean)/std

np.save("/content/drive/MyDrive/emg_mean.npy", mean)
np.save("/content/drive/MyDrive/emg_std.npy", std)

from sklearn.model_selection import train_test_split

x_train, x_test, y_train, y_test = train_test_split(x_data, y_data, test_size=0.2, stratify=y_data, random_state=42)

print(x_train.shape)
print(x_test.shape)

import torch
from torch.utils.data import TensorDataset, DataLoader

x_train = torch.tensor(x_train,dtype=torch.float32)
x_test = torch.tensor(x_test, dtype=torch.float32)
y_train = torch.tensor(y_train, dtype=torch.long)
y_test = torch.tensor(y_test, dtype = torch.long)

train_dataset = TensorDataset(x_train, y_train)
test_dataset = TensorDataset(x_test, y_test)

train_loader =DataLoader(train_dataset, batch_size=32, shuffle=True)
test_loader = DataLoader(test_dataset, batch_size=32, shuffle=False)

import torch.nn as nn


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

loss_function = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

for epoch in range(15):
  model.train()
  total_loss = 0

  for val, label in train_loader:
    optimizer.zero_grad()

    output = model(val)
    loss = loss_function(output, label)
    loss.backward()
    optimizer.step()

    total_loss += loss.item()

  print(f"Epoch {epoch+1}, Loss: {total_loss/len(train_loader):.4f}")

torch.save(model.state_dict(), "/content/drive/MyDrive/emg_CNN.pth")

model.eval()
all_preds=[]
all_labels = []

with torch.no_grad():
  for val, label in test_loader:
    output = model(val)
    _, predicted = torch.max(output,1)

    all_preds.extend(predicted.cpu().numpy())
    all_labels.extend(label.cpu().numpy())


  all_preds = np.array(all_preds)
  all_labels = np.array(all_labels)


from sklearn.metrics import confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns

classes = np.unique(all_labels)

for cls in classes:
  cls_index = all_labels == cls
  crt = np.sum(all_preds[cls_index]==cls)
  total = np.sum(cls_index)

  print("Class :", cls)
  print("Correct: ", crt)
  print("total :", total)
  print("Accuracy :", crt/total)

conf_mat = confusion_matrix(all_labels, all_preds)
print("Confusion Matrix : \n", conf_mat)

plt.figure(figsize = (5,4))
sns.heatmap(conf_mat, annot = True, fmt = "d", cmap = "Blues")
plt.xlabel("Predicted")
plt.ylabel("True")
plt.show()
