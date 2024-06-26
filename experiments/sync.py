import ray
import time
from parameter_servers.server_actor import ParameterServer
from workers.worker_task import compute_gradients
from metrics.metric_exporter import MetricExporter
# from models.test_model import get_data_loader, evaluate
from models.fashion_mnist import fashion_mnist_get_data_loader
from models.model_common import evaluate

iterations = 200
num_workers = 2

def run_sync(model, num_workers=1, epochs=5, server_kill_timeout=10, server_recovery_timeout=5, kill_times=1):
  metric_exporter = MetricExporter.remote("sync control")
  ps = ParameterServer.remote(1e-2)

  test_loader = fashion_mnist_get_data_loader()[1]

  print("Running synchronous parameter server training.")
  current_weights = ps.get_weights.remote()
  for i in range(iterations * epochs):
    gradients = [compute_gradients.remote(current_weights, metric_exporter=metric_exporter) for _ in range(num_workers)]
    # Calculate update after all gradients are available.
    current_weights = ps.apply_gradients.remote(gradients, metric_exporter)

    if i % 10 == 0:
        # Evaluate the current model.
        model.set_weights(ray.get(current_weights))
        accuracy, loss = evaluate(model, test_loader)
        print("Time {}: \taccuracy is {:.3f}\tloss is {:.3f}".format(int(time.time()), accuracy, loss))
        metric_exporter.set_accuracy.remote(accuracy)

  print("Time {}: \taccuracy is {:.3f}\tloss is {:.3f}".format(int(time.time()), accuracy, loss))


  # Clean up Ray resources and processes before the next example.
  ray.shutdown()