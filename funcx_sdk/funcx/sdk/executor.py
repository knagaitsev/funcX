import time
import threading
import os
import asyncio
import uuid
from concurrent.futures import Future
import concurrent
import logging
import websockets
from websockets.exceptions import InvalidHandshake
import janus
import multiprocessing as mp

logger = logging.getLogger(__name__)


class FuncXExecutor(concurrent.futures.Executor):
    """ An executor
    """

    def __init__(self, funcx_client,
                 results_ws_uri: str = 'ws://localhost:6000',
                 label: str = 'FuncXExecutor',
                 auto_start: bool = True):
        """
        Parameters
        ==========

        funcx_client : client object
            Instance of FuncXClient to be used by the executor

        results_ws_uri : str
            Web sockets URI for the results

        label : str
            Optional string label to name the executor.
            Default: 'FuncXExecutor'

        auto_start : Bool
            Set this to start the result poller thread at init. If disabled the poller thread
            must be started by calling FuncXExecutor_object.start()
            Default: True
        """

        self.funcx_client = funcx_client
        self.results_ws_uri = results_ws_uri
        self.label = label
        self._tasks = {}
        self._function_registry = {}
        self._function_future_map = {}
        self._kill_event = threading.Event()
        self.task_group_id = str(uuid.uuid4())  # we need to associate all batch launches with this id
        if auto_start:
            self.start()

    def start(self):
        """ Start the result polling threads
        """

        # Currently we need to put the batch id's we launch into this queue
        # to tell the web_socket_poller to listen on them. Later we'll associate

        self.task_group_queue = mp.Queue()
        # self.task_future_queue = janus.Queue()
        # async_task_future_q = self.task_future_queue.async_q
        loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.web_socket_poller,
                                       args=(self._kill_event, loop, ))

        asyncio.run_coroutine_threadsafe(self.handle_task(), loop)

        # self.task_future_queue.sync_q.put_nowait(1)

        self.thread.start()
        logger.debug("Started web_socket_poller thread")

    async def handle_task(self):
        print('c')

    def web_socket_poller(self, kill_event, loop):
        asyncio.set_event_loop(loop)

        loop.create_task(self.run_ws())
        loop.create_task(self.receive_info())
        loop.run_forever()

    async def run_ws(self):
        print('a')
        return
    
    async def receive_info(self):
        print('b')
        return
        # while True:
        #     task_future = await async_task_future_q.get()
        #     print(task_future)

    def submit(self, function, *args, endpoint_id=None, container_uuid=None, **kwargs):
        """Initiate an invocation

        Parameters
        ----------
        function : Function/Callable
            Function / Callable to execute

        *args : Any
            Args as specified by the function signature

        endpoint_id : uuid str
            Endpoint UUID string. Required

        **kwargs : Any
            Arbitrary kwargs

        Returns
        -------
        Future : concurrent.futures.Future
            A future object
        """

        if function not in self._function_registry:
            # Please note that this is a partial implementation, not all function registration
            # options are fleshed out here.
            logger.debug("Function:{function} is not registered. Registering")
            function_uuid = self.funcx_client.register_function(function,
                                                                function_name=function.__name__,
                                                                container_uuid=container_uuid)
            self._function_registry[function] = function_uuid
            logger.debug(f"Function registered with id:{function_uuid}")
        assert endpoint_id is not None, "endpoint_id key-word argument must be set"

        batch = self.funcx_client.create_batch(batch_id=self.task_group_id)
        batch.add(*args,
                  endpoint_id=endpoint_id,
                  function_id=self._function_registry[function],
                  **kwargs)
        r = self.funcx_client.batch_run(batch)
        logger.debug(f"Batch submitted to task_group: {self.task_group_id}")

        task_uuid = r[0]
        # There's a potential for a race-condition here where the result reaches
        # the poller before the future is added to the future_map
        self._function_future_map[task_uuid] = Future()

        return self._function_future_map[task_uuid]

    def shutdown(self):

        self._kill_event.set()
        logger.debug(f"Executor:{self.label} shutting down")


def double(x):
    return x * 2


if __name__ == '__main__':

    from funcx import FuncXClient
    from funcx import set_stream_logger
    import time

    set_stream_logger()
    fx = FuncXExecutor(FuncXClient(funcx_service_address='http://localhost:5000/v2'))

    # endpoint_id = 'c6c7888a-1134-40a7-b062-8f3ecfc4b6c2'
    # future = fx.submit(double, 5, endpoint_id=endpoint_id)

    # for i in range(5):
    #     time.sleep(1)
    #     # Non-blocking check whether future is done
    #     print("Is the future done? :", future.done())

    # print("This next blocking call will fail with a TimeoutError because the backend isn't working")
    # future.result(timeout=2)     # <--- This is a blocking call
