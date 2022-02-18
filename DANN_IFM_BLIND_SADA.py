import os
import time
import numpy as np
from math import sqrt

class DANN(object):
    
    def __init__(self, learning_rate=0.001, hidden_layer_size=25, lambda_adapt=1., maxiter=200,  
                 epsilon_init=None, adversarial_representation=True, seed=12342, verbose=False):
        """
        Domain Adversarial Neural Network for classification
        
        option "learning_rate" is the learning rate of the neural network.
        option "hidden_layer_size" is the hidden layer size.
        option "lambda_adapt" weights the domain adaptation regularization term.
                if 0 or None or False, then no domain adaptation regularization is performed
        option "maxiter" number of training iterations.
        option "epsilon_init" is a term used for initialization.
                if None the weight matrices are weighted by 6/(sqrt(r+c))
                (where r and c are the dimensions of the weight matrix)
        option "adversarial_representation": if False, the adversarial classifier is trained
                but has no impact on the hidden layer representation. The label predictor is
                then the same as a standard neural-network one (see experiments_moon.py figures). 
        option "seed" is the seed of the random number generator.
        """
        
        self.hidden_layer_size = hidden_layer_size
        self.maxiter = maxiter
        self.lambda_adapt = lambda_adapt if lambda_adapt not in (None, False) else 0.
        self.epsilon_init = epsilon_init
        self.learning_rate = learning_rate
        self.adversarial_representation = adversarial_representation
        self.seed = seed
        self.verbose = verbose
            
    def sigmoid(self, z):
        """
        Sigmoid function.
        
        """
        return 1. / (1. + np.exp(-z))
    
    def softmax(self, z):
        """
        Softmax function.
        
        """
        v = np.exp(z)
        return v / np.sum(v,axis=0)

    def predict_test_loss(self, X, y_hot):
        """
         Compute and return the label predictions for X, i.e., a 1D array of size len(X).
         the ith row of the array contains the predicted class for the ith example .
        """
        output_layer = self.forward(X)
        return - np.mean(np.mean(y_hot * np.log(output_layer), axis = 0))

       
    def random_init(self, l_in, l_out):
        """
        This method is used to initialize the weight matrices of the DA neural network 
        
        """
        if self.epsilon_init is not None:
            epsilon = self.epsilon_init 
        else:
            epsilon = sqrt(6.0 / (l_in + l_out))
            
        return epsilon * (2 * np.random.rand(l_out, l_in) - 1.0)
       
    def fit(self, X, Y, Y_domain, X_adapt, Y_valid, Yt_domain, X_valid=None, do_random_init=True):
        """         
        Trains the domain adversarial neural network until it reaches a total number of
        iterations of "self.maxiter" since it was initialize.
        inputs:
              X : Source data matrix
              Y : Source labels
              X_adapt : Target data matrix
              (X_valid, Y_valid) : validation set used for early stopping.
              do_random_init : A boolean indicating whether to use random initialization or not.
        """
        
        nb_examples, nb_features = np.shape(X)
        action_labels = len(set(Y))
        subj_labels = len(set(Y_domain))
        nb_examples_adapt, _ = np.shape(X_adapt)

        if self.verbose:
            print('[DANN parameters]', self.__dict__)
        
        np.random.seed(self.seed)
        
        if do_random_init:
            W = self.random_init(nb_features, self.hidden_layer_size)
            V = self.random_init(self.hidden_layer_size, action_labels)
            b = np.zeros(self.hidden_layer_size)
            c = np.zeros(action_labels)
            U = self.random_init(self.hidden_layer_size, subj_labels)
            d = np.zeros(subj_labels)
        else:
            W, V, b, c, U, d = self.W, self.V, self.b, self.c, self.U, self.d 
            
        best_valid_risk = 2.0
        continue_until = 30
        y_valid_hot = np.zeros( ( action_labels, len(Y_valid) ) )
        y_valid_hot[Y_valid.astype(int), np.arange(len(Y_valid))] = 1.0
        f = open('res_loss' +str(int(Yt_domain[0]))+'.txt','w')	
        f1 = open('res_acc' +str(int(Yt_domain[0]))+'.txt','w')
        for t in range(self.maxiter):
            if t % 200 ==0:
              print (t)
            for i in range(nb_examples):
                
                x_t, y_t, s_t = X[i,:], Y[i], Y_domain[i]
                hidden_layer = self.sigmoid(np.dot(W, x_t) + b)
                output_layer = self.softmax(np.dot(V, hidden_layer) + c)
                y_hot = np.zeros(action_labels)
                y_hot[int(y_t)] = 1.0
                if t!=0:
                    train_loss = - np.sum(y_hot * np.log(output_layer))
                    test_loss = self.predict_test_loss(X_adapt, y_valid_hot)
                    pred_label_test = self.predict(X_adapt)
                    test_acc=np.sum(pred_label_test==Y_valid)/float(len(Y_valid))
                    pred_label_train = self.predict(X)
                    train_acc=np.sum(pred_label_train==Y)/float(len(Y))
                    f.write(str(train_loss)+'\t'+str(test_loss)+ '\n')
                    f1.write(str(train_acc)+'\t'+str(test_acc)+ '\n')
                 
                delta_c = output_layer - y_hot  
                delta_V = np.dot(delta_c.reshape(-1,1), hidden_layer.reshape(1,-1)) 
                delta_b = np.dot(V.T, delta_c) * hidden_layer * (1.-hidden_layer) 
                delta_W = np.dot(delta_b.reshape(-1,1), x_t.reshape(1,-1)) 
                
                if self.lambda_adapt == 0.:
                    delta_U, delta_d = 0., 0.
                else:
                    # add domain adaptation regularizer from current domain
                    #gho_x_t = self.sigmoid(np.dot(U.T, hidden_layer) + d)
                    gho_x_t = self.softmax(np.dot(U, hidden_layer) + d)
                    subj_hot=np.zeros(subj_labels)
                    subj_hot[int(s_t)]=1.0
                    delta_d = self.lambda_adapt * (subj_hot - gho_x_t) 
                    delta_U = np.dot(delta_d.reshape(-1,1), hidden_layer.reshape(1,-1))

                    if self.adversarial_representation:
                        tmp = np.dot(U.T,self.lambda_adapt * (subj_hot - gho_x_t))*hidden_layer * (1.-hidden_layer)
                        delta_b += tmp
                        delta_W += np.dot(tmp.reshape(-1,1), x_t.reshape(1,-1))
                    
          
                W -= delta_W * self.learning_rate
                b -= delta_b * self.learning_rate
     
                V -= delta_V * self.learning_rate
                c -= delta_c * self.learning_rate
                
                U += delta_U * self.learning_rate 
                d += delta_d * self.learning_rate 
            # END for i in range(nb_examples)

            self.W, self.V, self.b, self.c, self.U, self.d = W, V, b, c, U, d
            
            # early stopping
            if X_valid is not None:
                valid_pred = self.predict(X_valid)
                valid_risk = np.mean( valid_pred != Y_valid )
                if valid_risk <= best_valid_risk:
                    if self.verbose: 
                        print('[DANN best valid risk so far] %f (iter %d)' % (valid_risk, t))
                    best_valid_risk = valid_risk
                    best_weights = (W.copy(), V.copy(), b.copy(), c.copy())
                    best_t = t
                    continue_until = max(continue_until, int(1.5*t))
                elif t > continue_until: 
                    if self.verbose: 
                        print('[DANN early stop] iter %d' % t)
                    break
        # END for t in range(self.maxiter)
        
        if X_valid is not None:
            self.W, self.V, self.b, self.c = best_weights
            self.nb_iter = best_t
            self.valid_risk = best_valid_risk
        else:
            self.nb_iter = self.maxiter
            self.valid_risk = 2.
            
    def forward(self, X):
        """
         Compute and return the network outputs for X, i.e., a 2D array of size len(X) by len(set(Y)).
         the ith row of the array contains output probabilities for each class for the ith example.
         
        """
        hidden_layer = self.sigmoid(np.dot(self.W, X.T) + self.b[:,np.newaxis])
        output_layer = self.softmax(np.dot(self.V, hidden_layer) + self.c[:,np.newaxis])
        return output_layer

    def hidden_representation(self, X):
        """
         Compute and return the network hidden layer values for X.
        """
        hidden_layer = self.sigmoid(np.dot(self.W, X.T) + self.b[:,np.newaxis])
        return hidden_layer.T

    def predict(self, X):
        """
         Compute and return the label predictions for X, i.e., a 1D array of size len(X).
         the ith row of the array contains the predicted class for the ith example .
        """
        output_layer = self.forward(X)
        return np.argmax(output_layer, 0)

    def predict_domain(self, X):
        """
         Compute and return the domain predictions for X, i.e., a 1D array of size len(X).
         the ith row of the array contains the predicted domain (0 or 1) for the ith example.
        """
        hidden_layer = self.sigmoid(np.dot(self.W, X.T) + self.b[:, np.newaxis])
        output_layer = self.sigmoid(np.dot(self.U, hidden_layer) + self.d)
        return np.array(output_layer < .5, dtype=int)
