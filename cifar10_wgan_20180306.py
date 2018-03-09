import numpy as np
import tensorflow as tf
import pickle
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import os
from load_cifar10 import load_CIFAR10

cifar10_dir = 'data/cifar-10-batches-py'
X_train, y_train, X_test, y_test = load_CIFAR10(cifar10_dir)
X = np.concatenate((X_train,X_test))
y = np.concatenate((y_train,y_test))

from sklearn.preprocessing import MinMaxScaler
minmax = MinMaxScaler()
X_rows = X.reshape(X.shape[0], 32 * 32 * 3)
X = minmax.fit_transform(X_rows)
X = X.reshape(X.shape[0], 32, 32, 3)





def get_inputs(noise_dim, image_height, image_width, image_depth):
    inputs_real = tf.placeholder(tf.float32, [None, image_height, image_width, image_depth], name='inputs_real')
    inputs_noise = tf.placeholder(tf.float32, [None, noise_dim], name='inputs_noise')
    return inputs_real, inputs_noise


def get_generator(noise_img, output_dim, is_train=True, alpha=0.01):
    with tf.variable_scope("generator", reuse=(not is_train)):
        # 100 x 1 to 4 x 4 x 512
        # 全连接层
        layer1 = tf.layers.dense(noise_img, 4 * 4 * 512)
        layer1 = tf.reshape(layer1, [-1, 4, 4, 512])
        # batch normalization
        layer1 = tf.layers.batch_normalization(layer1, training=is_train)
        # Leaky ReLU
        layer1 = tf.maximum(alpha * layer1, layer1)
        # dropout
        layer1 = tf.nn.dropout(layer1, keep_prob=0.8)

        # 4 x 4 x 512 to 8 x 8 x 256
        layer2 = tf.layers.conv2d_transpose(layer1, 256, 4, strides=2, padding='same')
        layer2 = tf.layers.batch_normalization(layer2, training=is_train)
        layer2 = tf.maximum(alpha * layer2, layer2)
        layer2 = tf.nn.dropout(layer2, keep_prob=0.8)

        # 8 x 8 256 to 16 x 16 x 128
        layer3 = tf.layers.conv2d_transpose(layer2, 128, 3, strides=2, padding='same')
        layer3 = tf.layers.batch_normalization(layer3, training=is_train)
        layer3 = tf.maximum(alpha * layer3, layer3)
        layer3 = tf.nn.dropout(layer3, keep_prob=0.8)

        # 16 x 16 x 128 to 32 x 32 x 3
        logits = tf.layers.conv2d_transpose(layer3, output_dim, 3, strides=2, padding='same')
        outputs = tf.tanh(logits)

        return outputs


def get_discriminator(inputs_img, reuse=False, alpha=0.01):
    with tf.variable_scope("discriminator", reuse=reuse):
        # 32 x 32 x 3 to 16 x 16 x 128
        # 第一层不加入BN
        layer1 = tf.layers.conv2d(inputs_img, 128, 3, strides=2, padding='same')
        layer1 = tf.maximum(alpha * layer1, layer1)
        layer1 = tf.nn.dropout(layer1, keep_prob=0.8)

        # 16 x 16 x 128 to 8 x 8 x 256
        layer2 = tf.layers.conv2d(layer1, 256, 3, strides=2, padding='same')
        layer2 = tf.layers.batch_normalization(layer2, training=True)
        layer2 = tf.maximum(alpha * layer2, layer2)
        layer2 = tf.nn.dropout(layer2, keep_prob=0.8)

        # 8 x 8 x 256 to 4 x 4 x 512
        layer3 = tf.layers.conv2d(layer2, 512, 3, strides=2, padding='same')
        layer3 = tf.layers.batch_normalization(layer3, training=True)
        layer3 = tf.maximum(alpha * layer3, layer3)
        layer3 = tf.nn.dropout(layer3, keep_prob=0.8)

        # 4 x 4 x 512 to 4*4*512 x 1
        flatten = tf.reshape(layer3, (-1, 4 * 4 * 512))
        logits = tf.layers.dense(flatten, 1)

        return logits


def get_loss(inputs_real, inputs_noise, image_depth, smooth=0.1):
    g_outputs = get_generator(inputs_noise, image_depth, is_train=True)
    d_logits_real = get_discriminator(inputs_real)
    d_logits_fake = get_discriminator(g_outputs, reuse=True)

    g_loss = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(logits=d_logits_fake,
                                                                    labels=tf.ones_like(d_logits_fake)))

    d_loss_real = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(logits=d_logits_real,
                                                                         labels=tf.ones_like(d_logits_real)))
    d_loss_fake = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(logits=d_logits_fake,
                                                                         labels=tf.zeros_like(d_logits_fake)))
    d_loss = tf.add(d_loss_real, d_loss_fake)
    tf.summary.scalar('D_loss', d_loss)
    tf.summary.scalar('G_loss', g_loss)
    summ = tf.summary.merge_all()
    return g_loss, d_loss, summ


def get_optimizer(g_loss, d_loss, learning_rate=0.001):

    train_vars = tf.trainable_variables()

    g_vars = [var for var in train_vars if var.name.startswith("generator")]
    d_vars = [var for var in train_vars if var.name.startswith("discriminator")]

    # Optimizer
    with tf.control_dependencies(tf.get_collection(tf.GraphKeys.UPDATE_OPS)):
        g_opt = tf.train.RMSPropOptimizer(learning_rate).minimize(g_loss, var_list=g_vars)
        d_opt = tf.train.RMSPropOptimizer(learning_rate).minimize(d_loss, var_list=d_vars)

    clip_discriminator_var_op = [var.assign(tf.clip_by_value(var, -0.01,0.01)) for var in d_vars]
    return g_opt, d_opt, clip_discriminator_var_op

# def plot_images(samples,e):
#     samples = (samples + 1) / 2
#     fig, axes = plt.subplots(nrows=1, ncols=10, sharex=True, sharey=True, figsize=(30,2))
#     for img, ax in zip(samples, axes):
#         ax.imshow(img.reshape((32, 32, 3)), cmap='Greys_r')
#         ax.get_xaxis().set_visible(False)
#         ax.get_yaxis().set_visible(False)
#     fig.tight_layout(pad=0)
#     plt.savefig('epochs'+str(e)+'.jpg')

def show_generator_output(sess, n_images, inputs_noise, output_dim):

    cmap = 'Greys_r'
    noise_shape = inputs_noise.get_shape().as_list()[-1]
    # 生成噪声图片
    examples_noise = np.random.uniform(-1, 1, size=[n_images, noise_shape])

    samples = sess.run(get_generator(inputs_noise, output_dim, False),
                       feed_dict={inputs_noise: examples_noise})
    return samples

batch_size = 1024
noise_size = 100
epochs = 10000
n_samples = 80
learning_rate = 0.001
beta1 = 0.4

images = X[y==4]


def train(noise_size, data_shape, batch_size, n_samples):
    steps = 0
    inputs_real, inputs_noise = get_inputs(noise_size, data_shape[1], data_shape[2], data_shape[3])
    g_loss, d_loss, summ  = get_loss(inputs_real, inputs_noise, data_shape[-1])
    g_train_opt, d_train_opt, clip_opt = get_optimizer(g_loss, d_loss,  learning_rate)

    with tf.Session() as sess:
        sess.run(tf.global_variables_initializer())
        writer = tf.summary.FileWriter('./graphs', sess.graph)

        # 迭代epoch
        for e in range(epochs):
            for batch_i in range(images.shape[0] // batch_size - 1):
                steps += 1
                batch_images = images[batch_i * batch_size: (batch_i + 1) * batch_size]
                # scale to -1, 1
                batch_images = batch_images * 2 - 1
                # noise
                batch_noise = np.random.uniform(-1, 1, size=(batch_size, noise_size))
                # run optimizer

                _ = sess.run(d_train_opt, feed_dict={inputs_real: batch_images,
                                                     inputs_noise: batch_noise})
                _ = sess.run(clip_opt)

                _ = sess.run(g_train_opt, feed_dict={inputs_real: batch_images,
                                                     inputs_noise: batch_noise})
                D_loss, G_loss, summm = sess.run([d_loss, g_loss,summ],feed_dict={inputs_real: batch_images,
                                                     inputs_noise: batch_noise})
                writer.add_summary(summm)
            train_loss_d = d_loss.eval({inputs_real: batch_images,
                                        inputs_noise: batch_noise})
            train_loss_g = g_loss.eval({inputs_real: batch_images,
                                        inputs_noise: batch_noise})
            if e % 500 == 0:
                print("Epoch {}/{}....".format(e, epochs),
                      "Discriminator Loss: {:.4f}....".format(train_loss_d),
                      "Generator Loss: {:.4f}....".format(train_loss_g))
            if e % 500 ==0:
                samples = show_generator_output(sess, n_samples, inputs_noise, data_shape[-1])
                samples = (samples + 1) / 2
                fig, axes = plt.subplots(nrows=4, ncols=20, sharex=True, sharey=True, figsize=(80, 16))
                imgs = samples[:80]
                for image, row in zip([imgs[:20], imgs[20:40], imgs[40:60], imgs[60:80]], axes):
                    for img, ax in zip(image, row):
                        ax.imshow(img)
                        ax.get_xaxis().set_visible(False)
                        ax.get_yaxis().set_visible(False)
                fig.tight_layout(pad=0.1)
                plt.savefig('4wgan-ep' + str(e) + '.jpg')

with tf.Graph().as_default():
    train(noise_size, [-1, 32, 32, 3], batch_size, n_samples)
