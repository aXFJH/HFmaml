from sklearn.datasets import fetch_mldata
from tqdm import trange
import numpy as np
import random
import json
import os

# Setup directory for train/test data
train_path = './data/train/all_data_0_niid_0_keep_10_train_9.json'
test_path = './data/test/all_data_0_niid_0_keep_10_test_9.json'
dir_path = os.path.dirname(train_path)
if not os.path.exists(dir_path):
    os.makedirs(dir_path)
dir_path = os.path.dirname(test_path)
if not os.path.exists(dir_path):
    os.makedirs(dir_path)

def prepare_mnist_data():
    # Get MNIST data, normalize, and divide by level
    mnist = fetch_mldata('MNIST original', data_home='./data')
    print(mnist.data.shape)
    mu = np.mean(mnist.data.astype(np.float32), 0)
    sigma = np.std(mnist.data.astype(np.float32), 0)
    mnist.data = (mnist.data.astype(np.float32) - mu)/(sigma+0.001)
    mnist_data = []
    mnist_label = []
    for i in trange(10):
        idx = mnist.target==i
        mnist_data.append(mnist.data[idx])
        mnist_label.append(mnist.target[idx])
    return mnist_data,mnist_label

def generateNIID(data_list,label_list):
    '''
    data_list是一个list，里面保存的是每个类别的数据，例如mnist就是10个类别，data_list就存了10个元素，
    每个元素是一个ndarray,每个ndarray存的是一个类别的样本，是展开存储的，每一行是一个样本
    :param data_list: an ndarray
    :param label_list:
    :return:
    '''
    # print([len(v) for v in mnist_data])
    # print(mnist_label[2])

    ###### CREATE USER DATA SPLIT #######
    # Assign 10 samples to each user
    X = [[] for _ in range(100)]
    y = [[] for _ in range(100)]
    idx = np.zeros(10, dtype=np.int64)
    for user in range(100):
        for j in range(2):
            l = (user+j)%10
            X[user] += data_list[l][idx[l]:idx[l]+5].tolist()
            #y[user] += (l*np.ones(5)).tolist()
            y[user] += label_list[l][idx[l]:idx[l]+5].tolist()
            idx[l] += 5
            #print(y[user])
    print(idx)

    # Assign remaining sample by power law
    user = 0
    props = np.random.lognormal(0, 0.2, (10,100,2)) #change 2.0 to 0.2
    props = np.array([[[len(v)-4500]] for v in data_list])*props/np.sum(props,(1,2), keepdims=True)#change 100 to 5000
    #idx = 1000*np.ones(10, dtype=np.int64)
    for user in trange(100):
        for j in range(2):
            l = (user+j)%10
            num_samples = int(props[l,user//10,j])
            #print(num_samples)
            if idx[l] + num_samples < len(data_list[l]):
                X[user] += data_list[l][idx[l]:idx[l]+num_samples].tolist()
                #y[user] += (l*np.ones(num_samples)).tolist()
                y[user] += label_list[l][idx[l]:idx[l]+num_samples].tolist()
                idx[l] += num_samples

    print(idx)

    # Create data structure
    train_data = {'users': [], 'user_data': {}, 'num_samples': []}
    test_data = {'users': [], 'user_data': {}, 'num_samples': []}

    # Setup 100 users
    for i in trange(100, ncols=120):
        uname = 'f_{0:05d}'.format(i)

        combined = list(zip(X[i], y[i]))
        random.shuffle(combined)
        X[i][:], y[i][:] = zip(*combined)
        num_samples = len(X[i])
        #train_len = int(0.9*num_samples)
        train_len = 5
        test_len = num_samples - train_len

        train_data['users'].append(uname)
        train_data['user_data'][uname] = {'x': X[i][:train_len], 'y': y[i][:train_len]}
        train_data['num_samples'].append(train_len)
        test_data['users'].append(uname)
        test_data['user_data'][uname] = {'x': X[i][train_len:], 'y': y[i][train_len:]}
        test_data['num_samples'].append(test_len)

    print(train_data['num_samples'])
    print(test_data['num_samples'])
    print(sum(train_data['num_samples']))
    print(sum(test_data['num_samples']))

    with open(train_path,'w') as outfile:
        json.dump(train_data, outfile)
    with open(test_path, 'w') as outfile:
        json.dump(test_data, outfile)

data,label=prepare_mnist_data()

print(type(data[0]))
print(len(data))
print(data[0].shape)