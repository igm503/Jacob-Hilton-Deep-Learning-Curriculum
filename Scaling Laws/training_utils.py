from model import model
import numpy as np
import torch
import torch.nn as nn
import torchvision
import torchvision.transforms as transforms
import torch.optim as optim
from tqdm import tqdm
import math
import pandas as pd

def evaluate(testloader, net, criterion, device):
    with torch.no_grad():
        running_loss = 0
        for batch_num, data in enumerate(testloader):
            inputs, labels = data[0].to(device), data[1].to(device)
            outputs = net(inputs)
            loss = criterion(outputs, labels)
            running_loss += loss.item()
    return running_loss / (batch_num + 1)

def log(net, model_size, batch_size, device, test_loader, base_rate, criterion, train_loss, df, step):
    net.eval()
    eval_loss = evaluate(test_loader, net, criterion, device)
    df.loc[len(df.index)] = [base_rate, model_size, step * batch_size, train_loss, eval_loss]
    net.train()

def keep_least(df, group_var, min_var):
    minimum = 1e9
    min_list = []
    group = df[group_var][0]
    for i in range(len(df)):
        if math.isclose(group, df[group_var][i]):
            minimum = min(minimum, df[min_var][i])
        else:
            minimum = df[min_var][i]
            group = df[group_var][i]
        min_list.append(minimum)
    return min_list

def add_vars(df, batch_size):
    df['eval_min'] = keep_least(df, 'model_size', 'eval_loss')
    df['train_min'] = keep_least(df, 'model_size', 'train_loss')
    df['compute'] = (df['model_size'] **2)  * df['step'] * batch_size
    df['params'] = round((df['model_size'] ** 2), 0)

def train_one_epoch(net, model_size, batch_size, device, train_loader, test_loader, base_rate, optimizer, criterion, df, log_type, log_interval):
    for step, data in tqdm(enumerate(train_loader)):
        inputs, labels = data[0].to(device), data[1].to(device)
        optimizer.zero_grad(set_to_none=True)
        outputs = net(inputs)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        if (step + 1) % log_interval == 0:
            train_loss = loss.item()
            log(net, model_size, batch_size, device, test_loader, base_rate, criterion, train_loss, df, step)

def train(model_size, batch_size, device, data_augment, base_rate, df, log_type, log_interval):
    train_loader, test_loader = MNIST_dataloaders(data_augment, batch_size)
    net = model(model_size)
    net = net.to(device)
    criterion = nn.CrossEntropyLoss()
    rate = base_rate / np.sqrt(model_size)
    optimizer = optim.Adam(net.parameters(), lr=rate, betas=(0.9, 0.98), eps=1e-9)
    train_one_epoch(net, model_size, batch_size, device, train_loader, test_loader, base_rate, optimizer, criterion, df, log_type, log_interval)

def run_test(df, log_type, log_interval, test_values, num_tests=1, model_size=1, batch_size=128, base_rate=0.01, data_augment=1, device='mps'):
    for i in range(num_tests):
        if log_type == 'lr':
            for lr in tqdm(test_values):
                train(model_size, batch_size, device, data_augment, lr, df, log_type, log_interval)
        elif log_type == 's':
            for size in tqdm(test_values):
                train(size, batch_size, device, data_augment, base_rate, df, log_type, log_interval)
        else:
            print('Invalid log_type. Must be \'s\' or \'lr\'')
    add_vars(df, batch_size)

def MNIST_dataloaders(data_augment, batch_size):
    # Training Data
    transform = transforms.Compose([transforms.ToTensor(), transforms.Normalize(0, 1)])
    trainset = [torchvision.datasets.MNIST(root='./data', train=True, download=True,
                                             transform=transform) for i in range(data_augment)]                       
    trainset = torch.utils.data.ConcatDataset(trainset)
    train_loader = torch.utils.data.DataLoader(trainset, batch_size=batch_size,
                                            shuffle=True, num_workers=2, persistent_workers=True)
    # Eval Data
    test_data = torchvision.datasets.MNIST(root='./data', train=False, download=True, transform=transform)
    test_loader = torch.utils.data.DataLoader(test_data, batch_size=128, shuffle=False, num_workers=2, persistent_workers=True)

    return train_loader, test_loader