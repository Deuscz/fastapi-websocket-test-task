import logging
import os
import time
import shutil


class WorkerCoordinator:
    """
    Worker Coordinator for graceful shutdown management.
    Each worker writes an ALIVE file on startup and a DONE file on graceful shutdown.
    The last worker to finish notifies the master process to exit.
    """

    def __init__(self, pid, shutdown_dir, timeout):
        """ Initialize the WorkerCoordinator. """
        self.PID = pid
        self.shutdown_dir = shutdown_dir
        self.timeout = timeout
        shutil.rmtree(self.shutdown_dir, ignore_errors=True)
        self.shutdown_dir.mkdir(parents=True, exist_ok=True)
        self.alive_file = self.shutdown_dir / f"worker-{self.PID}.alive"
        self.done_file = self.shutdown_dir / f"worker-{self.PID}.done"
        self.logger = logging.getLogger("worker_coordinator")

    def list_alive_files(self):
        """ List all ALIVE files in the shutdown directory. """
        return list(self.shutdown_dir.glob("worker-*.alive"))

    def list_done_files(self):
        return list(self.shutdown_dir.glob("worker-*.done"))

    def block_until_all_done(self, poll_interval):
        """
        Blocking wait — do NOT return until:
        len(done_files) == len(alive_files)
        This deliberately blocks the process so that the Uvicorn master does not
        treat this worker as 'exited' prematurely.
        """
        start = time.time()
        while True:
            alive = len(self.list_alive_files())
            done = len(self.list_done_files())
            self.logger.info(
                f"[coord] waiting: done {done}/{alive} (pid={self.PID})")

            if done >= alive:
                self.logger.info(
                    "[coord] all workers completed graceful shutdown")
                return

            if (time.time() - start) > self.timeout:
                self.logger.warning(
                    "[coord] max_wait exceeded while waiting for other workers")
                return

            time.sleep(poll_interval)

    def create_alive_file(self):
        """ Create the ALIVE file for this worker. """
        try:
            time.sleep(2)
            self.alive_file.write_text("alive")
        except Exception:
            self.logger.exception("[coord] failed to write alive file")

    def try_shutdown_master(self):
        """ Send SIGTERM to the parent/master process (best-effort). """
        try:
            os._exit(1)
        except PermissionError:
            self.logger.exception(
                "[coord] permission error sending SIGTERM to master")
        except Exception:
            self.logger.exception("[coord] failed to signal master")

    def exit_application(self):
        """
        Called when this worker completes graceful_shutdown.
        Writes DONE file and then blocks until every worker that started has written DONE.
        The last worker will notify the master to terminate.
        """
        try:
            self.done_file.write_text("done")
        except Exception:
            self.logger.exception("[coord] failed to write done file")

        self.block_until_all_done(poll_interval=5)

        self.try_shutdown_master()
        self.logger.info(
            "[exit] exit_application returning; waiting for master to finish termination")
