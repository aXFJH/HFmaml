import numpy as np
import argparse
import importlib
import random
import os
import tensorflow as tf
from flearn.utils.model_utils import read_data, read_data_xin

from flearn.models.client import Client
from tqdm import tqdm
from scipy import io

from main_HFfmaml import prepare_dataset
from utils.utils import save_result

os.environ['TF_CPP_MIN_LOG_LEVEL']='3'

# GLOBAL PARAMETERS
OPTIMIZERS = ['HFfmaml', 'fmaml', 'fedavg', 'fedprox', 'feddane', 'fedddane', 'fedsgd']
DATASETS = ['sent140', 'nist', 'shakespeare', 'mnist',
            'synthetic_iid', 'synthetic_0_0', 'synthetic_0.5_0.5', 'synthetic_1_1','cifar10','cifar100','Fmnist']  # NIST is EMNIST in the paepr

MODEL_PARAMS = {
    'sent140.bag_dnn': (2,),  # num_classes
    'sent140.stacked_lstm': (25, 2, 100),  # seq_len, num_classes, num_hidden
    'sent140.stacked_lstm_no_embeddings': (25, 2, 100),  # seq_len, num_classes, num_hidden
    'nist.mclr': (62,),  # num_classes, should be changed to 62 when using EMNIST
    'mnist.mclr': (10),  # num_classes change
    'Fmnist.mclr': (10),
    'mnist.mclr2': (10),
    'mnist.mclrFed': (10),
    'Fmnist.mclrFed': (10),
'Fmnist.cnn_fedavg': (10,),
    'mnist.cnn': (10,),  # num_classes
    'cifar10.cnn_fedavg': (10,),
    'cifar100.cnn_fedavg': (100,),
    'shakespeare.stacked_lstm': (80, 80, 256),  # seq_len, emb_dim, num_hidden
    'synthetic_fed.mclr': (10),  # num_classes changed, remove,
    'synthetic.mclr2': (10),  # num_classes changed, remove,
    'synthetic.mclrFed': (10)
}


def read_options():
    ''' Parse command line arguments or load defaults '''
    parser = argparse.ArgumentParser()

    parser.add_argument('--optimizer', default='fedavg', help='name of optimizer;', type=str, choices=OPTIMIZERS)
    parser.add_argument('--dataset', default='cifar100', help='name of dataset;', type=str, choices=DATASETS)
    parser.add_argument('--model', default='cnn_fedavg', help='name of model;', type=str)
    parser.add_argument('--num_rounds', default=100, help='number of rounds to simulate;', type=int)
    parser.add_argument('--eval_every', default=1, help='evaluate every rounds;', type=int)
    parser.add_argument('--clients_per_round', default=40, help='number of clients trained per round;', type=int)
    parser.add_argument('--batch_size', default=10, help='batch size when clients train on data;', type=int)
    parser.add_argument('--num_epochs', default=5, help='number of epochs when clients train on data;', type=int)  # 20
    parser.add_argument('--alpha', default=0.01, help='learning rate for inner solver;', type=float)
    parser.add_argument('--beta', default=0.003, help='meta rate for inner solver;', type=float)
    # parser.add_argument('--mu',help='constant for prox;',type=float,default=0.01)
    parser.add_argument('--seed', default=0, help='seed for randomness;', type=int)
    parser.add_argument('--labmda', default=0, help='labmda for regularizer', type=int)
    parser.add_argument('--rho', default=1.5, help='rho for regularizer', type=int)
    parser.add_argument('--mu_i', default=0, help='mu_i for optimizer', type=int)
    parser.add_argument('--num_local_updates', default=1, help='mu_i for optimizer', type=int)
    parser.add_argument('--adapt_num', default=1, help='mu_i for optimizer', type=int)
    parser.add_argument('--R', default=0, help='the R th test', type=int)
    parser.add_argument('--logdir', default='./log', help='the R th test', type=str)
    parser.add_argument('--transfer', default=False, help='Pretrain to get theta_c', type=bool)
    parser.add_argument('--pretrain', default=False, help='Pretrain to get theta_c', type=bool)

    try:
        parsed = vars(parser.parse_args())
    except IOError as msg:
        parser.error(str(msg))

    # Set seeds------
    random.seed(1 + parsed['seed'])
    np.random.seed(12 + parsed['seed'])
    tf.set_random_seed(123 + parsed['seed'])

    # load selected model
    if parsed['dataset'].startswith("synthetic"):  # all synthetic_fed datasets use the same model
        model_path = '%s.%s.%s.%s' % ('flearn', 'models', 'synthetic', parsed['model'])  # changed
    elif parsed['dataset']=="cifar10":
        model_path = '%s.%s.%s.%s' % ('flearn', 'models', 'cifar10', parsed['model'])  # changed
    elif parsed['dataset']=="cifar100":
        model_path = '%s.%s.%s.%s' % ('flearn', 'models', 'cifar100', parsed['model'])  # changed
    elif parsed['dataset']=="Fmnist":
        model_path = '%s.%s.%s.%s' % ('flearn', 'models', 'Fmnist', parsed['model'])
    else:
        model_path = '%s.%s.%s.%s' % ('flearn', 'models', 'mnist', parsed['model'])  # parsed['dataset']

    print('@line 80 model_path:',model_path)
    mod = importlib.import_module(model_path)
    learner = getattr(mod, 'Model')

    # load selected trainer
    opt_path = 'flearn.trainers.%s' % parsed['optimizer']
    mod = importlib.import_module(opt_path)
    optimizer = getattr(mod, 'Server')

    # add selected model parameter
    parsed['num_classes'] = MODEL_PARAMS['.'.join(model_path.split('.')[2:])]

    # print and return
    maxLen = max([len(ii) for ii in parsed.keys()]);
    fmtString = '\t%' + str(maxLen) + 's : %s';
    print('Arguments:')
    for keyPair in sorted(parsed.items()): print(fmtString % keyPair)

    return parsed, learner, optimizer


def reshape_label(label,n=10):
    # print(label)
    new_label = [0] * n
    new_label[int(label)] = 1
    return new_label


def reshape_features(x):
    x = np.array(x)
    x = np.transpose(x.reshape(3, 32, 32), [1, 2, 0])
    # print(x.shape)
    return x

def reshapeFmnist(x):
    x=np.array(x)
    x=x.reshape(28,28,1)
    return x

def main():
    tf.reset_default_graph()
    # suppress tf warnings
    tf.logging.set_verbosity(tf.logging.WARN)

    # parse command line arguments
    options, learner, optimizer = read_options()
    test_user, dataset = prepare_dataset(options)

    # 、 o00000007理论 call appropriate trainer
    theta_c_path = '/root/TC174611125/fmaml/fmaml_mac/theta_c/{}_theata_c.mat'.format(options['dataset'])
    t = optimizer(options, learner,theta_c_path, dataset,test_user)
    loss_history,acc_history=t.train()
    loss_save_path='losses_OPT_{}_Dataset{}_round_{}_L{}_R{}.mat'.format(options['optimizer'],
                                                                     options['dataset'],
                                                                     options['num_rounds'],
                                                                     options['num_epochs'],
                                                                     options['R'])
    acc_save_path = 'Accuracies_OPT_{}_Dataset{}_round_{}_L{}_R{}.mat'.format(options['optimizer'],
                                                                          options['dataset'],
                                                                          options['num_rounds'],
                                                                          options['num_epochs'],
                                                                          options['R'])
    loss_save_path=os.path.join(options['logdir'],loss_save_path)
    acc_save_path=os.path.join(options['logdir'],acc_save_path)

    io.savemat(
        loss_save_path,
        {'losses': loss_history})
    io.savemat(
        acc_save_path,
        {'accuracies': acc_history})
    print('after training, start testing')

    client_params = t.latest_model
    weight = client_params

    loss_test,acc_test=target_test(test_user, learner, dataset, options, weight)
    loss_test_forget, acc_test_forget = target_test(test_user, learner, dataset, options, weight,situation='forget_test')
    tqdm.write(' Final loss: {}'.format(np.sum(loss_test)))
    print("Local average acc", np.sum(acc_test))
    print("acc_test_forget acc", np.sum(acc_test_forget))

    print('loss_save_path',loss_save_path)
    print('acc_save_path', acc_save_path)
    result_path = os.path.join(options['logdir'],
                               'contrast_{}_{}_{}_L{}.csv'.format(options['model'], options['dataset'],
                                                                  options['optimizer'], options['num_epochs']))
    save_result(result_path, [[np.sum(acc_test),acc_test_forget, acc_save_path,loss_save_path]],
                col_name=['Accuracy','acc_test_forget', 'acc_save_path','loss_save_path'])

def target_test(test_user,learner,dataset,options,weight,situation='normal_train'):
    if situation=='forget_test':
        test_user, dataset = prepare_dataset(options,situation)
    loss_test = dict()
    accs = dict()
    num_test = dict()
    for i, user in enumerate(test_user):
        # print(dataset[2][user])
        loss_test[i], accs[i], num_test[i] = fmaml_test(learner=learner, train_data=dataset[2][user],
                                                     test_data=dataset[3][user],
                                                     params=options, user_name=user, weight=weight)
    loss_test = list(loss_test.values())
    accs = list(accs.values())
    num_test = list(num_test.values())
    loss_test = [l * n / np.sum(num_test) for l, n in zip(loss_test, num_test)]
    acc_test = [a * n / np.sum(num_test) for a, n in zip(accs, num_test)]
    return loss_test,acc_test

def fmaml_test(learner, train_data, test_data, params, user_name, weight):
    print('fmaml test')

    # client_params = trainer.latest_model
    client_model = learner(params)  # changed remove star

    test_client = Client(user_name, [], train_data, test_data, client_model)
    test_client.set_params(weight)

    _ = test_client.fast_adapt(params['adapt_num'])

    acc, test_loss, test_num, preds = test_client.test_test()

    return test_loss, acc, test_num


if __name__ == '__main__':
    main()
