"""Run a program in a subprocess. Automatically restart it when a file changes.

This is a simple program that will launch another program in a subprocess
and restart that program if any files are detected as changed.


The primary use for this is with skaffold. Skaffold will automatically sync
files to the container; but we need to restart the program in order to pick
up those changes.

Example usage
run_with_auto_restart.py --directory=/src/dir1 --directory=/src/dir2 -- /program/to/run --arg1=b
"""
import argparse
import subprocess
import time
import logging
from watchdog.observers import Observer
from watchdog.events import LoggingEventHandler

class RestartEventHandler(LoggingEventHandler):
  def __init__(self, command):
    """Create the handler.

    Args:
      command: The command to run.
    """
    super(RestartEventHandler, self).__init__()
    self._command = command
    self._p = None
    self.restart()

  def restart(self):
    if self._p:
      logging.info("Terminating the current process")
      self._p.terminate()


    logging.info(f"Starting a proces to run command: {' '.join(self._command)}")
    self._p = subprocess.Popen(self._command)

  def on_any_event(self, event):
    super().on_any_event(event)
    self.restart()

if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

  parser = argparse.ArgumentParser(description="Run and auto restart.")
  parser.add_argument('--directory', dest="directories",
                        action="append",
                        help="A directory to watch for changes.")

  args, unparsed = parser.parse_known_args()

  # Remove "--" as an argument
  while True:
    if unparsed[0].strip() == "--":
      del unparsed[0]
      continue
    break

  event_handler = RestartEventHandler(unparsed)
  observer = Observer()
  for d in args.directories:
    logging.info(f"Watching {d}")
    observer.schedule(event_handler, d, recursive=True)
  observer.start()
  try:
    while True:
      if event_handler._p:
        if event_handler._p.poll() is not None:
          # TODO(jlewi): would it be better to exit to force a container restart
          logging.info("Process has terminated restarting it")
          event_handler.restart()
      time.sleep(1)
  except KeyboardInterrupt:
    observer.stop()
  observer.join()

