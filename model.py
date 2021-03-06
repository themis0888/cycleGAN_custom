from __future__ import division
import os
import time
from glob import glob
import tensorflow as tf
import numpy as np
from collections import namedtuple
from PIL import Image as im
import numpy as np
import pdb
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from module import *
from utils import *


class cyclegan(object):
    def __init__(self, sess, args):
        self.sess = sess
        self.batch_size = args.batch_size
        self.image_size = args.fine_size
        self.input_c_dim = args.input_nc
        self.output_c_dim = args.output_nc
        self.L1_lambda = args.L1_lambda
        self.dataset_dir = args.dataset_dir
        self.data_path = args.data_path
        self.print_freq = args.print_freq

        self.discriminator = discriminator
        if args.use_resnet:
            self.generator = generator_resnet
        else:
            self.generator = generator_unet
        if args.use_lsgan:
            self.criterionGAN = mae_criterion
        else:
            self.criterionGAN = sce_criterion
        if args.nsml:
            import nsml

        OPTIONS = namedtuple('OPTIONS', 'batch_size image_size \
                              gf_dim df_dim output_c_dim is_training')
        self.options = OPTIONS._make((args.batch_size, args.fine_size,
                                      args.ngf, args.ndf, args.output_nc,
                                      args.phase == 'train'))

        self._build_model()
        self.saver = tf.train.Saver()
        self.pool = ImagePool(args.max_size)


    def _build_model(self):
        self.real_data = tf.placeholder(tf.float32,
                                        [None, self.image_size, self.image_size,
                                         self.input_c_dim + self.output_c_dim],
                                        name='real_A_and_B_images')

        self.real_A = self.real_data[:, :, :, :self.input_c_dim]
        self.real_B = self.real_data[:, :, :, self.input_c_dim:self.input_c_dim + self.output_c_dim]

        self.fake_B = self.generator(self.real_A, self.options, False, name="generatorA2B")
        self.fake_A_ = self.generator(self.fake_B, self.options, False, name="generatorB2A")
        self.fake_A = self.generator(self.real_B, self.options, True, name="generatorB2A")
        self.fake_B_ = self.generator(self.fake_A, self.options, True, name="generatorA2B")

        self.DB_fake = self.discriminator(self.fake_B, self.options, reuse=False, name="discriminatorB")
        self.DA_fake = self.discriminator(self.fake_A, self.options, reuse=False, name="discriminatorA")
        self.g_loss_a2b = self.criterionGAN(self.DB_fake, tf.ones_like(self.DB_fake)) \
            + self.L1_lambda * abs_criterion(self.real_A, self.fake_A_) \
            + self.L1_lambda * abs_criterion(self.real_B, self.fake_B_)
        self.g_loss_b2a = self.criterionGAN(self.DA_fake, tf.ones_like(self.DA_fake)) \
            + self.L1_lambda * abs_criterion(self.real_A, self.fake_A_) \
            + self.L1_lambda * abs_criterion(self.real_B, self.fake_B_)
        self.gan_loss = self.criterionGAN(self.DA_fake, tf.ones_like(self.DA_fake)) \
            + self.criterionGAN(self.DB_fake, tf.ones_like(self.DB_fake))
        self.L1_loss = self.L1_lambda * abs_criterion(self.real_A, self.fake_A_) \
            + self.L1_lambda * abs_criterion(self.real_B, self.fake_B_)
        self.g_loss = self.gan_loss + self.L1_loss

        self.fake_A_sample = tf.placeholder(tf.float32,
                                            [None, self.image_size, self.image_size,
                                             self.input_c_dim], name='fake_A_sample')
        self.fake_B_sample = tf.placeholder(tf.float32,
                                            [None, self.image_size, self.image_size,
                                             self.output_c_dim], name='fake_B_sample')
        self.DB_real = self.discriminator(self.real_B, self.options, reuse=True, name="discriminatorB")
        self.DA_real = self.discriminator(self.real_A, self.options, reuse=True, name="discriminatorA")
        self.DB_fake_sample = self.discriminator(self.fake_B_sample, self.options, reuse=True, name="discriminatorB")
        self.DA_fake_sample = self.discriminator(self.fake_A_sample, self.options, reuse=True, name="discriminatorA")

        self.db_loss_real = self.criterionGAN(self.DB_real, tf.ones_like(self.DB_real))
        self.db_loss_fake = self.criterionGAN(self.DB_fake_sample, tf.zeros_like(self.DB_fake_sample))
        self.db_loss = (self.db_loss_real + self.db_loss_fake) / 2
        self.da_loss_real = self.criterionGAN(self.DA_real, tf.ones_like(self.DA_real))
        self.da_loss_fake = self.criterionGAN(self.DA_fake_sample, tf.zeros_like(self.DA_fake_sample))
        self.da_loss = (self.da_loss_real + self.da_loss_fake) / 2
        self.d_loss = self.da_loss + self.db_loss

        self.g_loss_a2b_sum = tf.summary.scalar("g_loss_a2b", self.g_loss_a2b)
        self.g_loss_b2a_sum = tf.summary.scalar("g_loss_b2a", self.g_loss_b2a)
        self.g_loss_sum = tf.summary.scalar("g_loss", self.g_loss)
        self.g_sum = tf.summary.merge([self.g_loss_a2b_sum, self.g_loss_b2a_sum, self.g_loss_sum])
        self.db_loss_sum = tf.summary.scalar("db_loss", self.db_loss)
        self.da_loss_sum = tf.summary.scalar("da_loss", self.da_loss)
        self.d_loss_sum = tf.summary.scalar("d_loss", self.d_loss)
        self.db_loss_real_sum = tf.summary.scalar("db_loss_real", self.db_loss_real)
        self.db_loss_fake_sum = tf.summary.scalar("db_loss_fake", self.db_loss_fake)
        self.da_loss_real_sum = tf.summary.scalar("da_loss_real", self.da_loss_real)
        self.da_loss_fake_sum = tf.summary.scalar("da_loss_fake", self.da_loss_fake)
        self.d_sum = tf.summary.merge(
            [self.da_loss_sum, self.da_loss_real_sum, self.da_loss_fake_sum,
             self.db_loss_sum, self.db_loss_real_sum, self.db_loss_fake_sum,
             self.d_loss_sum]
        )

        self.test_A = tf.placeholder(tf.float32,
                                     [None, self.image_size, self.image_size,
                                      self.input_c_dim], name='test_A')
        self.test_B = tf.placeholder(tf.float32,
                                     [None, self.image_size, self.image_size,
                                      self.output_c_dim], name='test_B')
        self.testB = self.generator(self.test_A, self.options, True, name="generatorA2B")
        self.testA = self.generator(self.test_B, self.options, True, name="generatorB2A")

        t_vars = tf.trainable_variables()
        self.d_vars = [var for var in t_vars if 'discriminator' in var.name]
        self.g_vars = [var for var in t_vars if 'generator' in var.name]
        for var in t_vars: print(var.name)

    def train(self, args):
        """Train cyclegan"""
        self.lr = tf.placeholder(tf.float32, None, name='learning_rate')
        self.d_optim = tf.train.AdamOptimizer(self.lr, beta1=args.beta1) \
            .minimize(self.d_loss, var_list=self.d_vars)
        self.g_optim = tf.train.AdamOptimizer(self.lr, beta1=args.beta1) \
            .minimize(self.g_loss, var_list=self.g_vars)

        init_op = tf.global_variables_initializer()
        self.sess.run(init_op)
        self.writer = tf.summary.FileWriter("./logs", self.sess.graph)

        counter = 1
        start_time = time.time()

        if args.continue_train:
            if self.load(args.checkpoint_dir):
                print(" [*] Load SUCCESS")
            else:
                print(" [!] Load failed...")
        # ./datasets/face2cartoon/
        for epoch in range(args.epoch):
            dataA = glob('{}{}/*.*'.format(self.data_path, self.dataset_dir + '/trainA'))
            dataB = glob('{}{}/*.*'.format(self.data_path, self.dataset_dir + '/trainB'))
            np.random.shuffle(dataA)
            np.random.shuffle(dataB)
            batch_idxs = min(min(len(dataA), len(dataB)), args.train_size) // self.batch_size
            lr = args.lr if epoch < args.epoch_step else args.lr*(args.epoch-epoch)/(args.epoch-args.epoch_step)

            for idx in range(0, batch_idxs):
                batch_files = list(zip(dataA[idx * self.batch_size:(idx + 1) * self.batch_size],
                                       dataB[idx * self.batch_size:(idx + 1) * self.batch_size]))
                batch_images = [load_train_data(batch_file, args.load_size, args.fine_size) for batch_file in batch_files]
                batch_images = np.array(batch_images).astype(np.float32)
                
                # Update G network and record fake outputs
                fake_A, fake_B, _, summary_str, gan_loss, L1_loss = self.sess.run(
                    [self.fake_A, self.fake_B, self.g_optim, self.g_sum, self.gan_loss, self.L1_loss],
                    feed_dict={self.real_data: batch_images, self.lr: lr})
                self.writer.add_summary(summary_str, counter)
                [fake_A, fake_B] = self.pool([fake_A, fake_B])

                # Update D network
                _, summary_str = self.sess.run(
                    [self.d_optim, self.d_sum],
                    feed_dict={self.real_data: batch_images,
                               self.fake_A_sample: fake_A,
                               self.fake_B_sample: fake_B,
                               self.lr: lr})
                self.writer.add_summary(summary_str, counter)

                counter += 1
                if np.mod(idx, 10) == 0:
                    print(("Epoch: [%2d] [%4d/%4d] time: %4.4f" % (
                        epoch, idx, batch_idxs, time.time() - start_time)))
                    print("GAN_loss: {0:.6f} \tL1_loss: {1:.6f}".format(gan_loss, L1_loss))

                if np.mod(counter, args.print_freq) == 0:
                    # self.sample_model(args.sample_dir, epoch, idx)
                    self.visualize(args.sample_dir, counter)

                if np.mod(counter, args.save_freq) == 0:
                    self.save(args.checkpoint_dir, counter)
                    if args.nsml == True:

                        nsml.save(epoch)

    def save(self, checkpoint_dir, step):
        model_name = "cyclegan.model"
        model_dir = "%s_%s" % (self.dataset_dir, self.image_size)
        checkpoint_dir = os.path.join(checkpoint_dir, model_dir)
        print(checkpoint_dir)
        if not os.path.exists(checkpoint_dir):
            os.makedirs(checkpoint_dir)

        self.saver.save(self.sess,
                        os.path.join(checkpoint_dir, model_name),
                        global_step=step)

    def load(self, checkpoint_dir):
        print(" [*] Reading checkpoint...")

        model_dir = "%s_%s" % (self.dataset_dir, self.image_size)
        checkpoint_dir = os.path.join(checkpoint_dir, model_dir)

        ckpt = tf.train.get_checkpoint_state(checkpoint_dir)
        if ckpt and ckpt.model_checkpoint_path:
            ckpt_name = os.path.basename(ckpt.model_checkpoint_path)
            self.saver.restore(self.sess, os.path.join(checkpoint_dir, ckpt_name))
            return True
        else:
            return False

    def visualize(self, sample_dir, counter, is_testing = False, args = None):
        
        if is_testing:
            init_op = tf.global_variables_initializer()
            self.sess.run(init_op)
            if self.load(args.checkpoint_dir):
                print(" [*] Load SUCCESS")
            else:
                print(" [!] Load failed...")

        num_input = 4
        num_col = 4
        dataA = glob('{}{}/*.*'.format(self.data_path, self.dataset_dir + '/trainA'))
        dataB = glob('{}{}/*.*'.format(self.data_path, self.dataset_dir + '/trainB'))
        np.random.shuffle(dataA)
        np.random.shuffle(dataB)
        fig=plt.figure(figsize=(8, 8))
        # pdb.set_trace()
        A2B, input_A = (self.testB, self.test_A) 
        B2A, input_B = (self.testA, self.test_B) 

        for i in range(num_input):

            input_files = list(dataA[(self.batch_size)*i:(self.batch_size)*(i+1)])
            sample_images = [load_test_data(input_file, self.image_size) for input_file in input_files]
            sample_images = np.array(sample_images).astype(np.float32)
            #pdb.set_trace()

            # fake_A, fake_B, rec_A, rec_B = self.sess.run([self.fake_A, self.fake_B, self.fake_A_, self.fake_B_], feed_dict={self.real_data: sample_images})
            OtoT = self.sess.run(A2B, feed_dict={input_A: sample_images})
            OtoTtoO = self.sess.run(B2A, feed_dict={input_B: OtoT})
            fig.add_subplot(num_input, num_col, num_col*i+1)
            plt.imshow((sample_images[0,:,:,:3]+1)/2)
            fig.add_subplot(num_input, num_col, num_col*i+2)
            plt.imshow((OtoT[0,:,:,:3]+1)/2)
            key_layer = np.repeat(np.expand_dims(OtoT[0,:,:,-1], axis=-1), 3, axis=2)

            fig.add_subplot(num_input, num_col, num_col*i+3)
            plt.imshow((OtoT[0,:,:,:3]+key_layer+2)/4)
            fig.add_subplot(num_input, num_col, num_col*i+4)
            plt.imshow((OtoTtoO[0,:,:,:3]+1)/2)


        plt.savefig(os.path.join(sample_dir, 'A_{0:06d}.jpg'.format(int(counter/self.print_freq))))

        fig=plt.figure(figsize=(8, 8))
        # pdb.set_trace()

        for i in range(num_input):

            input_files = list(dataB[(self.batch_size)*i:(self.batch_size)*(i+1)])
            sample_images = [load_test_data(input_file, self.image_size) for input_file in input_files]
            sample_images = np.array(sample_images).astype(np.float32)

            # fake_A, fake_B, rec_A, rec_B = self.sess.run([self.fake_A, self.fake_B, self.fake_A_, self.fake_B_], feed_dict={self.real_data: sample_images})
            OtoT = self.sess.run(B2A, feed_dict={input_B: sample_images})
            OtoTtoO = self.sess.run(A2B, feed_dict={input_A: OtoT})
            fig.add_subplot(num_input, num_col, num_col*i+1)
            plt.imshow((sample_images[0,:,:,:3]+1)/2)
            fig.add_subplot(num_input, num_col, num_col*i+2)
            plt.imshow((OtoT[0,:,:,:3]+1)/2)
            key_layer = np.repeat(np.expand_dims(OtoT[0,:,:,-1], axis=-1), 3, axis=2)

            fig.add_subplot(num_input, num_col, num_col*i+3)
            plt.imshow((OtoT[0,:,:,:3]+key_layer+2)/4)
            fig.add_subplot(num_input, num_col, num_col*i+4)
            plt.imshow((OtoTtoO[0,:,:,:3]+1)/2)

        plt.savefig(os.path.join(sample_dir, 'B_{0:06d}.jpg'.format(int(counter/self.print_freq))))



    def test(self, args):
        """Test cyclegan"""
        init_op = tf.global_variables_initializer()
        self.sess.run(init_op)
        if args.which_direction == 'AtoB':
            sample_files = glob('{}{}/*.*'.format(self.data_path, self.dataset_dir + '/testA'))
        elif args.which_direction == 'BtoA':
            sample_files = glob('{}{}/*.*'.format(self.data_path, self.dataset_dir + '/testB'))
        else:
            raise Exception('--which_direction must be AtoB or BtoA')

        if self.load(args.checkpoint_dir):
            print(" [*] Load SUCCESS")
        else:
            print(" [!] Load failed...")

        # write html for visual comparison
        index_path = os.path.join(args.test_dir, '{0}_index.html'.format(args.which_direction))
        index = open(index_path, "w")
        index.write("<html><body><table><tr>")
        index.write("<th>name</th><th>input</th><th>output</th></tr>")

        out_var, in_var = (self.testB, self.test_A) if args.which_direction == 'AtoB' else (
            self.testA, self.test_B)


        for sample_file in sample_files[:30]:
            print('Processing image: ' + sample_file)
            sample_image = [load_test_data(sample_file, args.fine_size)]
            sample_image = np.array(sample_image).astype(np.float32)
            image_path = os.path.join(args.test_dir,
                                      '{0}_{1}'.format(args.which_direction, os.path.basename(sample_file)))
            fake_img = self.sess.run(out_var, feed_dict={in_var: sample_image})
            save_images(fake_img, [1, 1], image_path)
            
            if '.npy' in sample_file:
                npy_img = np.load(sample_file)
                disc_img = np.uint8(npy_img[:,:,:3])
                org_im = im.fromarray(disc_img)
                file_name = sample_file[:-4]+'.jpg'
            else:
                org_im = im.open(sample_file)
                file_name = sample_file
            org_im.save(os.path.join(args.test_dir,'{}'.format(os.path.basename(file_name))))
            index.write("<td>%s</td>" % os.path.basename(image_path))
            index.write("<td><img src='%s'></td>" % (sample_file if os.path.isabs(sample_file) else (
                '..' + os.path.sep + sample_file)))
            index.write("<td><img src='%s'></td>" % (image_path if os.path.isabs(image_path) else (
                '..' + os.path.sep + image_path)))
            index.write("</tr>")
        index.close()


    def reconstruct(self, args):
        """Test cyclegan"""
        init_op = tf.global_variables_initializer()
        self.sess.run(init_op)
        if args.which_direction == 'AtoBtoA':
            sample_files = glob('{}{}/*.*'.format(self.data_path, self.dataset_dir + '/testA'))
        elif args.which_direction == 'BtoAtoB':
            sample_files = glob('{}{}/*.*'.format(self.data_path, self.dataset_dir + '/testB'))
        else:
            raise Exception('--which_direction must be AtoB or BtoA')

        if self.load(args.checkpoint_dir):
            print(" [*] Load SUCCESS")
        else:
            print(" [!] Load failed...")

        # write html for visual comparison
        index_path = os.path.join(args.test_dir, '{0}_index.html'.format(args.which_direction))
        index = open(index_path, "w")
        index.write("<html><body><table><tr>")
        index.write("<th>name</th><th>input</th><th>output</th></tr>")

        out_var, in_var = (self.testB, self.test_A) if args.which_direction == 'AtoB' else (
            self.testA, self.test_B)
        BtoB, AtoA = (self.testB, self.test_A) if args.which_direction == 'BtoAtoB' else (
            self.testA, self.test_B)

        for sample_file in sample_files[:30]:
            print('Processing image: ' + sample_file)
            sample_image = [load_test_data(sample_file, args.fine_size)]
            sample_image = np.array(sample_image).astype(np.float32)
            image_path = os.path.join(args.test_dir,
                                      '{0}_{1}'.format(args.which_direction, os.path.basename(sample_file)))
            OtoT = self.sess.run(out_var, feed_dict={in_var: sample_image})
            OtoTtoO = self.sess.run(out_var, feed_dict={in_var: OtoT})
            save_images(OtoTtoO, [1, 1], image_path)

            if '.npy' in sample_file:
                npy_img = np.load(sample_file)
                disc_img = np.uint8(npy_img[:,:,:3])
                org_im = im.fromarray(disc_img)
                file_name = sample_file[:-4]+'.jpg'
            else:
                org_im = im.open(sample_file)
                file_name = sample_file
            org_im.save(os.path.join(args.test_dir,'{}'.format(os.path.basename(file_name))))
            index.write("<td>%s</td>" % os.path.basename(image_path))
            index.write("<td><img src='%s'></td>" % (sample_file if os.path.isabs(sample_file) else (
                '..' + os.path.sep + sample_file)))
            index.write("<td><img src='%s'></td>" % (image_path if os.path.isabs(image_path) else (
                '..' + os.path.sep + image_path)))
            index.write("</tr>")
        index.close()
