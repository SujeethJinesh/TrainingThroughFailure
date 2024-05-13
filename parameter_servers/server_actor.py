import torch
import numpy as np
from models.test_model import ConvNet
import ray
import time
import os
from workers.worker_task import compute_gradients
from models.test_model import ConvNet, get_data_loader, evaluate
# from zookeeper.zoo import KazooChainNode

iterations = 400
num_workers = 2
weight_update_frequency = 10

@ray.remote(max_restarts=0)
class ParameterServer(object):
    def __init__(self, lr, model_saver=None, node_id=None):
        self.model = ConvNet()
        self.start_iteration = 0
        self.optimizer = torch.optim.SGD(self.model.parameters(), lr=lr)
        self.start_iteration = 0
        self.model_saver = model_saver
        if node_id is not None: 
          self.chain_node = KazooChainNode(node_id, [], self.retrieve_weights_from_zookeeper)

    def apply_gradients(self, gradients):
        grad = ray.get(gradients)
        summed_gradients = [
            np.stack(gradient_zip).sum(axis=0) for gradient_zip in zip(*grad)
        ]
        self.optimizer.zero_grad()
        self.model.set_gradients(summed_gradients)
        self.optimizer.step()
        return self.model.get_weights()

    def set_weights(self, weights, iteration_count):
        if weights:
          self.model.set_weights(weights)
          if self.model_saver:
            self.model_saver.set_weights_iteration_count.remote(weights, iteration_count)
          self.start_iteration = iteration_count

    def get_weights(self):
        return self.model.get_weights()

    def save_ckpoint(self):
      print('not implemented')
      # with tempfile.TemporaryDirectory() as temp_checkpoint_dir:
      #     checkpoint = None

      #     # Only the global rank 0 worker saves and reports the checkpoint
      #     if train.get_context().get_world_rank() == 0:
      #         ...  # Save checkpoint to temp_checkpoint_dir

      #         checkpoint = Checkpoint.from_directory(tmpdir)

      #     train.report(metrics, checkpoint=checkpoint)

    def run_training(self, synchronous=True):
      if synchronous:
        self.run_synch_chain_node_experiment()
      else:
        self.run_asynch_chain_node_experiment()

    def store_weights_in_zookeeper(self, weights, iteration):
      print("Node " + str(self.chain_node.node_id) + " starts storing weights")
      id_w = ray.put([weights, iteration + 1])
      pickled_weight_id = ray.cloudpickle.dumps(id_w)
      self.chain_node.zk.set("/base/" + str(self.chain_node.node_id), pickled_weight_id)

    def retrieve_weights_from_zookeeper(self, event):
      node_id = event.path[6]
      if event.type=='CHANGED' and int(node_id) < self.chain_node.node_id:
        retrieved_data = self.chain_node.zk.get("/base/" + node_id)
        unpickled_id_w_string = ray.cloudpickle.loads(retrieved_data[0])
        new_weights, iteration = ray.get(unpickled_id_w_string)
        self.model.set_weights(new_weights)
        self.start_iteration = iteration
        self.store_weights_in_zookeeper(new_weights, iteration)
        print("backup recieve weights")
        self.chain_node.zk.exists("/base/"+str(node_id), watch=self.chain_node.handle_delete_or_change_event)

    def run_synch_chain_node_experiment(self):
      test_loader = get_data_loader()[1]

      print("Running synchronous parameter server training.")
      current_weights = self.get_weights()
      for i in range(self.start_iteration, iterations):
          gradients = [compute_gradients.remote(current_weights) for _ in range(num_workers)]
          # Calculate update after all gradients are available.
          current_weights = self.apply_gradients(gradients)
          
          if i % weight_update_frequency == 0:
              self.store_weights_in_zookeeper(current_weights, i)
              # Evaluate the current model.
              self.set_weights(current_weights, i)
              accuracy = evaluate(self.model, test_loader)
              print("Iter {}: \taccuracy is {:.1f}".format(i, accuracy))

      print("Final accuracy is {:.1f}.".format(accuracy))

    def run_asynch_training(self):
      test_loader = get_data_loader()[1]

      print("Running Asynchronous Parameter Server Training.")
      current_weights = self.get_weights()
      gradients = []
      for _ in range(num_workers):
          gradients.append(compute_gradients.remote(current_weights))

      for i in range(self.start_iteration, iterations * num_workers):
          ready_gradient_list, _ = ray.wait(gradients)
          ready_gradient_id = ready_gradient_list[0]
          gradients.remove(ready_gradient_id)

          # Compute and apply gradients.
          current_weights = self.apply_gradients([ready_gradient_id])
          gradients.append(compute_gradients.remote(current_weights))

          if i % weight_update_frequency == 0:
              # Evaluate the current model after every 10 updates.
              self.set_weights(current_weights, i)
              accuracy = evaluate(self.model, test_loader)
              print("Iter {}: \taccuracy is {:.1f}".format(i, accuracy))

      print("Final accuracy is {:.1f}.".format(accuracy))

    def run_asynch_chain_node_experiment(self):
      test_loader = get_data_loader()[1]

      print("Running Asynchronous Parameter Server Training.")
      current_weights = self.get_weights()
      gradients = []
      for _ in range(num_workers):
          gradients.append(compute_gradients.remote(current_weights))

      for i in range(self.start_iteration, iterations * num_workers):
          ready_gradient_list, _ = ray.wait(gradients)
          ready_gradient_id = ready_gradient_list[0]
          gradients.remove(ready_gradient_id)

          # Compute and apply gradients.
          current_weights = self.apply_gradients([ready_gradient_id])
          gradients.append(compute_gradients.remote(current_weights))

          if i % weight_update_frequency == 0:
              # Evaluate the current model after every 10 updates.
              self.store_weights_in_zookeeper(current_weights, i)
              self.set_weights(current_weights, i)
              accuracy = evaluate(self.model, test_loader)
              print("Iter {}: \taccuracy is {:.1f}".format(i, accuracy))

      print("Final accuracy is {:.1f}.".format(accuracy))

    def run_asynch_chain_node_experiment(self):
      test_loader = get_data_loader()[1]

      print("Running Asynchronous Parameter Server Training.")
      current_weights = self.get_weights()
      gradients = []
      for _ in range(num_workers):
          gradients.append(compute_gradients.remote(current_weights))

      for i in range(self.start_iteration, iterations * num_workers):
          ready_gradient_list, _ = ray.wait(gradients)
          ready_gradient_id = ready_gradient_list[0]
          gradients.remove(ready_gradient_id)

          # Compute and apply gradients.
          current_weights = self.apply_gradients([ready_gradient_id])
          gradients.append(compute_gradients.remote(current_weights))

          if i % weight_update_frequency == 0:
              # Evaluate the current model after every 10 updates.
              self.store_weights_in_zookeeper(current_weights, i)
              self.set_weights(current_weights, i)
              accuracy = evaluate(self.model, test_loader)
              print("Iter {}: \taccuracy is {:.1f}".format(i, accuracy))

      print("Final accuracy is {:.1f}.".format(accuracy))

    def exit(self, sleep_sec):
        print("in exit method")
        time.sleep(sleep_sec)
        os._exit(0)
