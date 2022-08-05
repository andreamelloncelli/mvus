## Bug

L'ultimo output e' stato questo. Sembra che l'oggetto `src` sia vuoto, corretto?

```
cd /home/daco/dev/mvus ; /usr/bin/env /home/daco/dev/mvus/.venv/bin/python /home/daco/.vscode/extensions/ms-python.python-2022.10.1/pythonFiles/lib/python/debugpy/adapter/../../debugpy/launcher 37409 -- multiviewunsynch/main.py ./config.json
path_detect: data/drone-tracking-datasets/dataset4/detections/cam2.txt
path_detect: data/drone-tracking-datasets/dataset4/detections/cam3.txt
path_detect: data/drone-tracking-datasets/dataset4/detections/cam0.txt
path_detect: data/drone-tracking-datasets/dataset4/detections/cam1.txt
path_detect: data/drone-tracking-datasets/dataset4/detections/cam4.txt
path_detect: data/drone-tracking-datasets/dataset4/detections/cam5.txt
path_detect: data/drone-tracking-datasets/dataset4/detections/cam6.txt
Input data are loaded successfully, a scene is created.

The given corresponding frames are directly exploited as temporal synchronization


----------------- Bundle Adjustment with 2 cameras -----------------

Mean error of each camera before BA:    [125.5008 130.0244]
Number of BA parameters is 5094
Doing BA with 2 cameras...





Mean error of each camera after first BA:     [466.707  239.5237]
Number of BA parameters is 5094
Doing BA with 2 cameras...

/home/daco/dev/mvus/.venv/lib/python3.8/site-packages/numpy/core/fromnumeric.py:3432: RuntimeWarning: Mean of empty slice.
  return _methods._mean(a, axis=axis, dtype=dtype,
/home/daco/dev/mvus/.venv/lib/python3.8/site-packages/numpy/core/_methods.py:190: RuntimeWarning: invalid value encountered in double_scalars
  ret = ret.dtype.type(ret / rcount)

Mean error of each camera after second BA:     [   nan 21.595]

Total time: 0:07:01.640304




----------------- Bundle Adjustment with 3 cameras -----------------

Mean error of each camera before BA:    [      nan   21.8148 1732.1263]
Number of BA parameters is 5127
Doing BA with 3 cameras...


Mean error of each camera after first BA:     [      nan   21.8099 1725.47  ]
Traceback (most recent call last):
  File "/usr/lib/python3.8/runpy.py", line 194, in _run_module_as_main
    return _run_code(code, main_globals, None,
  File "/usr/lib/python3.8/runpy.py", line 87, in _run_code
    exec(code, run_globals)
  File "/home/daco/.vscode/extensions/ms-python.python-2022.10.1/pythonFiles/lib/python/debugpy/adapter/../../debugpy/launcher/../../debugpy/__main__.py", line 39, in <module>
    cli.main()
  File "/home/daco/.vscode/extensions/ms-python.python-2022.10.1/pythonFiles/lib/python/debugpy/adapter/../../debugpy/launcher/../../debugpy/../debugpy/server/cli.py", line 430, in main
    run()
  File "/home/daco/.vscode/extensions/ms-python.python-2022.10.1/pythonFiles/lib/python/debugpy/adapter/../../debugpy/launcher/../../debugpy/../debugpy/server/cli.py", line 284, in run_file
    runpy.run_path(target, run_name="__main__")
  File "/home/daco/.vscode/extensions/ms-python.python-2022.10.1/pythonFiles/lib/python/debugpy/_vendored/pydevd/_pydevd_bundle/pydevd_runpy.py", line 321, in run_path
    return _run_module_code(code, init_globals, run_name,
  File "/home/daco/.vscode/extensions/ms-python.python-2022.10.1/pythonFiles/lib/python/debugpy/_vendored/pydevd/_pydevd_bundle/pydevd_runpy.py", line 135, in _run_module_code
    _run_code(code, mod_globals, init_globals,
  File "/home/daco/.vscode/extensions/ms-python.python-2022.10.1/pythonFiles/lib/python/debugpy/_vendored/pydevd/_pydevd_bundle/pydevd_runpy.py", line 124, in _run_code
    exec(code, run_globals)
  File "multiviewunsynch/main.py", line 56, in <module>
    flight.remove_outliers(flight.sequence[:cam_temp],thres=flight.settings['thres_outlier'])
  File "/home/daco/dev/mvus/multiviewunsynch/reconstruction/common.py", line 714, in remove_outliers
    self.detection_to_global(i)
  File "/home/daco/dev/mvus/multiviewunsynch/reconstruction/common.py", line 126, in detection_to_global
    detect = self.cameras[i].undist_point(self.detections[i][1:]) if self.settings['undist_points'] else self.detections[i][1:]
  File "/home/daco/dev/mvus/multiviewunsynch/reconstruction/common.py", line 1154, in undist_point
    dst = cv2.undistortPoints(src, self.K, self.d)
cv2.error: OpenCV(4.6.0) /io/opencv/modules/calib3d/src/undistort.dispatch.cpp:396: error: (-215:Assertion failed) CV_IS_MAT(_src) && CV_IS_MAT(_dst) && (_src->rows == 1 || _src->cols == 1) && (_dst->rows == 1 || _dst->cols == 1) && _src->cols + _src->rows - 1 == _dst->rows + _dst->cols - 1 && (CV_MAT_TYPE(_src->type) == CV_32FC2 || CV_MAT_TYPE(_src->type) == CV_64FC2) && (CV_MAT_TYPE(_dst->type) == CV_32FC2 || CV_MAT_TYPE(_dst->type) == CV_64FC2) in function 'cvUndistortPointsInternal'
```
