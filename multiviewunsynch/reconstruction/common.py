# Classes that are common to the entire project
import numpy as np
from tools import util
import reconstruction.epipolar as ep
import cv2
import json
from datetime import datetime
from scipy.optimize import least_squares
from scipy import interpolate
from scipy.sparse import lil_matrix, vstack
from matplotlib import pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from tools import visualization as vis


class Scene:
    """ 
    Class that contains everything that we know about the scene, both measured and calculated data

    This class will contain all data and will be passed around to be changed and used by most methods. 

    Members
    -------
    cameras : list of elements of class Camera 
    detections : list of elements of class TrackedObject

    Methods
    -------

    """

    def __init__(self):
        """ 
        Default constructor, creates a Scene with no data
        """
        self.numCam = 0
        self.cameras = []
        self.detections = []
        self.detections_raw = []
        self.detections_global = []
        self.alpha = []
        self.beta = []
        self.traj = []
        self.sequence = []
        self.visible = []
        self.settings = []
        self.gps = []
        self.spline = {'tck':[], 'int':[]}
        self.rs = []
        self.ref_cam = 0
        self.find_order = True
        self.frame_id_all = []
        self.global_time_stamps_all = []
        self.global_detections = []
        self.global_traj = []
        

    def addCamera(self,*camera):
        """
        Adds one or more cameras to the scene, first it checks whether the passed object is an instance of Camera

        Parameters
        ----------
        camera : Camera
            the camera to be added
        """
        for i in camera:
            assert type(i) is Camera, "camera is not an instance of Camera"
            self.cameras.append(i)


    def addDetection(self,*detection):
        """
        Adds one or more detections to the scene.

        Parameters
        ----------
        detection : 
            2D detection in form of (frameId,x,y)*N
        """
        for i in detection:
            assert i.shape[0]==3, "Detection must in form of (x,y,frameId)*N"
            self.detections.append(i)


    def init_alpha(self,*prior):
        '''Initialize alpha for each camera based on the ratio of fps'''

        if len(prior):
            assert len(prior) == self.numCam, 'Number of input must be the same as the number of cameras'
            self.alpha = prior
        else:
            self.alpha = np.ones(self.numCam)
            fps_ref = self.cameras[self.ref_cam].fps
            for i in range(self.numCam):
                self.alpha[i] = fps_ref / self.cameras[i].fps


    def detection_to_global(self,*cam,motion=False):
        '''
        Convert frame indices of raw detections into the global timeline.

        Input is an iterable that specifies which detection(s) to compute.

        If no input, all detections will be converted.
        '''

        assert len(self.alpha)==self.numCam and len(self.beta)==self.numCam, 'The Number of alpha and beta is wrong'

        if len(cam):
            cams = cam
            if type(cams[0]) != int:
                cams = cams[0]
        else:
            cams = range(self.numCam)
            self.detections_global = [[] for i in cams]

        for i in cams:
            timestamp = self.alpha[i] * self.detections[i][0] + self.beta[i] + self.rs[i] * self.detections[i][2] / self.cameras[i].resolution[1]
            detect = self.cameras[i].undist_point(self.detections[i][1:]) if self.settings['undist_points'] else self.detections[i][1:]
            self.detections_global[i] = np.vstack((timestamp, detect))
            if motion:
                if (self.global_traj[1] == i).any():
                    # Update glob_traj timestamps for camera cam_id
                    #temp_cam_id = self.global_detections[1]
                    # Select global traj. points for current camera
                    temp_glob_traj = self.global_traj[:,self.global_traj[1] == i]
                    # Save traj. point locations in global_traj before update
                    temp_glob_traj_mask = np.isin(self.global_traj[3],temp_glob_traj[3])
                    # Select global det. points for current camera
                    temp_glob_det = self.global_detections[:,self.global_detections[0] == i]
                    # Save traj. point locations in global_traj
                    temp_glob_det_mask = np.isin(self.global_detections[2],temp_glob_det[2])
                    # Save camera detections that are used within the global traj. 
                    _,temp_glob_traj_idx,temp_glob_traj_det_idx = np.intersect1d(temp_glob_traj[2],self.detections[i][0],return_indices=True,assume_unique=True)
                    # Save camera detections that are used within the global det. 
                    _,temp_glob_det_idx,temp_det_idx = np.intersect1d(temp_glob_det[1],self.detections[i][0],return_indices=True,assume_unique=True)  
                    #temp_glob_traj[3] = self.detections_global[i][0,temp_det_idx]
                    #temp_glob_detections = self.global_detections[:,self.global_detections[1] == i]
                    #temp_glob_det_idx = temp_glob_detections[0].astype(int)
                    #temp_glob_traj_mask = np.isin(self.global_traj[0],temp_glob_det_idx)
                    #temp_glob_det_mask = np.isin(self.global_detections[0],temp_glob_traj[0])

                    assert np.sum(temp_glob_traj_mask == True) == len(temp_glob_traj_det_idx)
                    assert np.sum(temp_glob_det_mask == True) == len(self.detections_global[i][0])
                    # Update global detection timestamps for cam_id
                    self.global_detections[2,temp_glob_det_mask] = self.detections_global[i][0]
                    # Update global traj timestamps for detections in global_traj
                    self.global_traj[3,temp_glob_traj_mask] = self.detections_global[i][0,temp_glob_traj_det_idx]
        if motion:
            # Resort global_traj according to updated global timestamps 
            if not (self.global_traj[3,1:]>self.global_traj[3,:-1]).all():
                self.global_traj[:,np.argsort(self.global_traj[3,:])] 

    def cut_detection(self,second=1):
        '''
        Truncate the starting and end part of each continuous part of the detections
        '''

        if not second: return

        for i in range(self.numCam):
            detect = self.detections[i]
            interval = self.find_intervals(detect[0])
            cut = int(self.cameras[i].fps * second)

            interval_long = interval[:,interval[1]-interval[0]>cut*2]
            interval_long[0] += cut
            interval_long[1] -= cut

            assert (interval_long[1]-interval_long[0]>=0).all()

            self.detections[i], _ = self.sampling(detect,interval_long)

    
    def find_intervals(self,x,gap=5,idx=False):
        '''
        Given indices of detections, return a matrix that contains the start and the end of each
        continuous part.
        
        Input indices must be in ascending order. 
        
        The gap defines the maximal interruption, with which it's still considered as continuous. 
        '''

        assert len(x.shape)==1 and (x[1:]>x[:-1]).all(), 'Input must be an ascending 1D-array'

        # Compute start and end
        x_s, x_e = np.append(-np.inf,x), np.append(x,np.inf)
        start = x_s[1:] - x_s[:-1] >= gap
        end = x_e[:-1] - x_e[1:] <= -gap
        interval = np.array([x[start],x[end]])
        int_idx = np.array([np.where(start)[0],np.where(end)[0]])

        # Remove intervals that are too short
        mask = interval[1]-interval[0] >= gap
        interval = interval[:,mask]
        int_idx = int_idx[:,mask]

        assert (interval[0,1:]>interval[1,:-1]).all()

        if idx:
            return interval, int_idx
        else:
            return interval


    def sampling(self,x,interval,belong=False):
        '''
        Sample points from the input which are inside the given intervals
        '''

        # Define timestamps
        if len(x.shape)==1:
            timestamp = x
        elif len(x.shape)==2:
            assert x.shape[0]==3 or x.shape[0]==4, 'Input should be 1D array or 2D array with 3 or 4 rows'
            timestamp = x[0]

        # Sample points from each interval
        idx_ts = np.zeros_like(timestamp, dtype=int)
        for i in range(interval.shape[1]):
            mask = np.logical_xor(timestamp-interval[0,i] >= 0, timestamp-interval[1,i] >= 0)
            idx_ts[mask] = i+1

        if not belong:
            idx_ts = idx_ts.astype(bool)

        if len(x.shape)==1:
            return x[idx_ts.astype(bool)], idx_ts
        elif len(x.shape)==2:
            return x[:,idx_ts.astype(bool)], idx_ts
        else:
            raise Exception('The shape of input is wrong')


    def match_overlap(self,x,y):
        '''
        Given two inputs in the same timeline (global), return the parts of them which are temporally overlapped

        Important: it's assumed that x has a higher frequency (fps) so that points are interpolated in y
        '''

        interval = self.find_intervals(y[0])
        x_s, _ = self.sampling(x, interval)

        tck, u = interpolate.splprep(y[1:],u=y[0],s=0,k=3)
        y_s = np.asarray(interpolate.splev(x_s[0],tck))
        y_s = np.vstack((x_s[0],y_s))

        assert (x_s[0] == y_s[0]).all(), 'Both outputs should have the same timestamps'

        return x_s, y_s


    def init_traj(self,error=10,inlier_only=False):
        '''
        Select the first two cams in the sequence, compute fundamental matrix, triangulate points
        '''

        self.select_most_overlap(init=True)

        t1, t2 = self.sequence[0], self.sequence[1]
        K1, K2 = self.cameras[t1].K, self.cameras[t2].K

        # Find correspondences
        if self.cameras[t1].fps > self.cameras[t2].fps:
            d1, d2 = self.match_overlap(self.detections_global[t1], self.detections_global[t2])
        else:
            d2, d1 = self.match_overlap(self.detections_global[t2], self.detections_global[t1])
        
        # Compute fundamental matrix
        F,inlier = ep.computeFundamentalMat(d1[1:],d2[1:],error=error)
        E = np.dot(np.dot(K2.T,F),K1)

        if not inlier_only:
            inlier = np.ones(len(inlier))
        x1, x2 = util.homogeneous(d1[1:,inlier==1]), util.homogeneous(d2[1:,inlier==1])

        # Find corrected corresponding points for optimal triangulation
        N = d1[1:,inlier==1].shape[1]
        pts1=d1[1:,inlier==1].T.reshape(1,-1,2)
        pts2=d2[1:,inlier==1].T.reshape(1,-1,2)
        m1,m2 = cv2.correctMatches(F,pts1,pts2)
        x1,x2 = util.homogeneous(np.reshape(m1,(-1,2)).T), util.homogeneous(np.reshape(m2,(-1,2)).T)

        mask = np.logical_not(np.isnan(x1[0]))
        x1 = x1[:,mask]
        x2 = x2[:,mask]

        # Triangulte points
        X, P = ep.triangulate_from_E(E,K1,K2,x1,x2)
        self.traj = np.vstack((d1[0][inlier==1][mask],X[:-1]))

        # Assign the camera matrix for these two cameras
        self.cameras[t1].P = np.dot(K1,np.array([[1,0,0,0],[0,1,0,0],[0,0,1,0]]))
        self.cameras[t2].P = np.dot(K2,P)
        self.cameras[t1].decompose()
        self.cameras[t2].decompose()


    def traj_to_spline(self,smooth_factor=0.001):
        '''
        Convert discrete 3D trajectory into spline representation

        A single spline is built for each interval
        '''

        timestamp = self.traj[0]
        interval, idx = self.find_intervals(timestamp,idx=True)
        tck = [None] * interval.shape[1]

        for i in range(interval.shape[1]):
            part = self.traj[:,idx[0,i]:idx[1,i]+1]
            s = smooth_factor**2*len(part[0])
            try:
                tck[i], u = interpolate.splprep(part[1:],u=part[0],s=s,k=3)
            except:
                tck[i], u = interpolate.splprep(part[1:],u=part[0],s=s,k=1)
            
        self.spline['tck'], self.spline['int'] = tck, interval
        return self.spline


    def spline_to_traj(self,sampling_rate=1,t=None):
        '''
        Convert 3D spline into discrete 3D points

        Points are sampled either with a constant sampling rate or at the given timestamps t

        Outputs are 3D points
        '''
        
        tck, interval = self.spline['tck'], self.spline['int']
        self.traj = np.empty([4,0])

        if t is not None:
            assert len(t.shape)==1, 'Input timestamps must be a 1D array'
            timestamp = t
        else:
            timestamp = np.arange(interval[0,0], interval[1,-1], sampling_rate)

        for i in range(interval.shape[1]):
            t_part = timestamp[np.logical_and(timestamp>=interval[0,i], timestamp<=interval[1,i])]
            try:
                traj_part = np.asarray(interpolate.splev(t_part, tck[i]))
            except:
                continue
            self.traj = np.hstack((self.traj, np.vstack((t_part,traj_part))))

        assert (self.traj[0,1:] > self.traj[0,:-1]).all()

        return self.traj


    def error_cam(self,cam_id,mode='dist',motion=False,norm=False):
        '''
        Calculate the reprojection errors for a given camera

        Different modes are available: 'dist', 'xy_1D', 'xy_2D', 'each'
        '''

        tck, interval = self.spline['tck'], self.spline['int']
        if motion:
            self.detection_to_global(motion=motion)
        else:
            self.detection_to_global(cam_id)

        #if motion:
        #    _, idx = self.sampling(self.global_d,interval)
        #else:
        _, idx = self.sampling(self.detections_global[cam_id], interval, belong=True)
        detect = np.empty([3,0])
        point_3D = np.empty([3,0])
        for i in range(interval.shape[1]):
            detect_part = self.detections_global[cam_id][:,idx==i+1]
            if detect_part.size:
                if motion:
                    cam_global_traj = self.global_traj[:,self.global_traj[1] == cam_id]
                    #assert len(x.shape)==1 and (x[1:]>x[:-1]).all(), 'Input must be an ascending 1D-array'
                    #detect_idx = np.isin(detect_part[0],self.global_traj[3])
                    #traj_idx = np.isin(self.global_traj[3],detect_part[0])
                    _,traj_idx,detect_idx = np.intersect1d(cam_global_traj[3],detect_part[0],assume_unique=True,return_indices=True)
                    detect_part = detect_part[:,detect_idx]
                    detect = np.hstack((detect,detect_part))
                    point_3D = np.hstack((point_3D,cam_global_traj[4:,traj_idx]))
                else:
                    detect = np.hstack((detect,detect_part)) 
                    point_3D = np.hstack((point_3D, np.asarray(interpolate.splev(detect_part[0], tck[i]))))

        X = util.homogeneous(point_3D)
        x = detect[1:]
        x_cal = self.cameras[cam_id].projectPoint(X)
        # #Normalize Tracks
        if norm:
            x_cal = np.dot(np.linalg.inv(self.cameras[cam_id].K), x_cal)
            x = np.dot(np.linalg.inv(self.cameras[cam_id].K), util.homogeneous(x))

        if mode == 'dist':
            return ep.reprojection_error(x, x_cal)
        elif mode == 'xy_1D':
            return np.concatenate((abs(x_cal[0]-x[0]),abs(x_cal[1]-x[1])))
        elif mode == 'xy_2D':
            return np.vstack((abs(x_cal[0]-x[0]),abs(x_cal[1]-x[1])))
        elif mode == 'each':
            error_x = np.zeros_like(self.detections[cam_id][0])
            error_y = np.zeros_like(self.detections[cam_id][0])
            if motion:
                #mot_idx = np.isin(self.detections_global[cam_id][0],detect[0])
                #assert np.sum(mot_idx == True) == x_cal.shape[1], '# of detections and traj. points are not equal'
                _,det_idx,_ = np.intersect1d(self.detections_global[cam_id][0],detect[0],assume_unique=True,return_indices=True)
                assert det_idx.shape[0] == x_cal.shape[1], '# of detections and traj. points are not equal'
                error_x[det_idx] = abs(x_cal[0]-x[0])
                error_y[det_idx] = abs(x_cal[1]-x[1])
            else:
                error_x[idx.astype(bool)] = abs(x_cal[0]-x[0])
                error_y[idx.astype(bool)] = abs(x_cal[1]-x[1])
            return np.concatenate((error_x, error_y))

    def error_motion(self,cams,mode='dist',motion=False,norm=False,motion_weights=0):
        '''
        Calculate the reprojection errors for a given camera for a multi_spline object. 

        - Accounts for motion prior

        Different modes are available: 'dist', 'xy_1D', 'xy_2D', 'each'

        computes error for motion prior regularization
        '''

        tck, interval = self.spline['tck'], self.spline['int']
        self.detection_to_global(cams,motion=motion)
        _, idx = self.sampling(self.global_traj[3], interval, belong=True)

        detect = np.empty([3,0])
        point_3D = np.empty([3,0])
        temp_glob_ts = np.array([])
        mot_err_res = np.array([])
        mot_idx = np.array([]) 

        for i in range(interval.shape[1]):
            traj_part = self.global_traj[:,idx==i+1]
            if traj_part.size:
                weights = np.ones(traj_part.shape[1]) * motion_weights
                mot_err = self.motion_prior(traj_part[3:],weights)
                mot_err_res = np.concatenate((mot_err_res, mot_err))
                mot_idx = np.concatenate((mot_idx, traj_part[3,1:-1]))
                
        motion_error = np.zeros((self.global_traj.shape[1]))
        _,traj_idx,detect_idx = np.intersect1d(self.global_traj[3],mot_idx,assume_unique=True,return_indices=True)
        motion_error[traj_idx] = mot_err_res
        return motion_error
        
        # for i in range(interval.shape[1]):
        #     detect_part = self.detections_global[cam_id][:,idx==i+1]
        #     if detect_part.size:
                
    
        #     detect = np.hstack((detect,detect_part))
        #     point_3D = np.hstack((point_3D, np.asarray(interpolate.splev(detect_part[0], tck[i]))))
        # if motion:
        #     assert mot_err_res.shape[0] == mot_idx.shape[0], 'Motion prior indices are wrong shape'
        #     motion_error = np.zeros((self.detections[cam_id].shape[1]))
        #     motion_error[mot_idx.astype(int)] = mot_err_res

        # X = util.homogeneous(point_3D)
        # x = detect[1:]
        # x_cal = self.cameras[cam_id].projectPoint(X)

        # #Normalize Tracks
        # if norm:
        #     x_cal = np.dot(np.linalg.inv(self.cameras[cam_id].K), x_cal)
        #     x = np.dot(np.linalg.inv(self.cameras[cam_id].K), util.homogeneous(x))

        # if mode == 'dist':
        #     return ep.reprojection_error(x, x_cal)
        # elif mode == 'xy_1D':
        #     return np.concatenate((abs(x_cal[0]-x[0]),abs(x_cal[1]-x[1])))
        # elif mode == 'xy_2D':
        #     return np.vstack((abs(x_cal[0]-x[0]),abs(x_cal[1]-x[1])))
        # elif mode == 'each':
            
        #     error_x = np.zeros_like(self.detections[cam_id][0])
        #     error_y = np.zeros_like(self.detections[cam_id][0])

        #     if motion:
        #         _,idx3,_ = np.intersect1d(self.detections_global[cam_id][0],detect[0],return_indices=True,assume_unique=False)
        #         error_x[idx3.astype(int)] = abs(x_cal[0]-x[0])
        #         error_y[idx3.astype(int)] = abs(x_cal[1]-x[1])
            
        #     else:
        #         error_x[idx.astype(bool)] = abs(x_cal[0]-x[0])
        #         error_y[idx.astype(bool)] = abs(x_cal[1]-x[1])
            
        #     if motion:
        #             return np.concatenate((error_x, error_y)),motion_error
        #     else:
        #             return np.concatenate((error_x, error_y))

    def compute_visibility(self):
        '''
        Decide for each raw detection if it is visible from current 3D spline
        '''

        self.visible = []
        interval = self.spline['int']
        self.detection_to_global()

        for cam_id in range(self.numCam):
            _, visible = self.sampling(self.detections_global[cam_id], interval, belong=True)
            self.visible.append(visible)


    def BA(self, numCam, max_iter=10, rs=False,motion=False,motion_weights=1,norm=False):
        '''
        Bundle Adjustment with multiple splines

        The camera order is assumed to be the same as self.sequence
        '''

        def error_BA(x):
            '''
            Input is the model (parameters that need to be optimized)
            '''

            # Assign parameters to the class attributes
            sections = [numCam, numCam*2, numCam*3, numCam*3+numCam*num_camParam]
            model_parts = np.split(x, sections)
            self.alpha[self.sequence[:numCam]], self.beta[self.sequence[:numCam]], self.rs[self.sequence[:numCam]] = model_parts[0], model_parts[1], model_parts[2]

            cams = np.split(model_parts[3],numCam)
            for i in range(numCam):
                self.cameras[self.sequence[i]].vector2P(cams[i], calib=self.settings['opt_calib']) 
            
            if motion:
                self.global_traj[4:] = model_parts[4].reshape(-1,3).T

            else:
                spline_parts = np.split(model_parts[4],idx_spline[0,1:])
                for i in range(len(spline_parts)):
                    spline_i = spline_parts[i].reshape(3,-1)
                    self.spline['tck'][i][1] = [spline_i[0],spline_i[1],spline_i[2]]

            # Compute errors
            error = np.array([])
            for i in range(numCam):
                error_each = self.error_cam(self.sequence[i], mode='each',motion=motion,norm=norm)
                error = np.concatenate((error, error_each))
            if motion:
                error_motion = self.error_motion(self.sequence[:numCam],motion=motion,motion_weights=motion_weights)
                error = np.concatenate((error, error_motion))
            
            return error


        def jac_BA(near=3,motion_offset = 10):

            num_param = len(model)
            self.compute_visibility()
            jac = lil_matrix((1, num_param),dtype=int)
            #jac = np.empty([0,num_param])
            for i in range(numCam):
                cam_id = self.sequence[i]
                num_detect = self.detections[cam_id].shape[1]

                # consider only reprojection in x direction, which is the same in y direction
                jac_cam = lil_matrix((num_detect, num_param),dtype=int)
                #jac_cam = np.zeros((num_detect, num_param))

                if motion:
                    num_global_pnt = self.global_traj.shape[1]
                    m_jac = lil_matrix((num_global_pnt, num_param),dtype=int)

                # alpha and beta
                jac_cam[:,[i,i+numCam]] = 1

                # rolling shutter
                if rs:
                    jac_cam[:,i+numCam*2] = 1
                else:
                    jac_cam[:,i+numCam*2] = 0

                # camera parameters
                start = 3*numCam+i*num_camParam
                jac_cam[:,start:start+num_camParam] = 1

                if motion:
                    traj_start = numCam * (3+num_camParam)
                    traj_len = self.global_traj.shape[1]
                    for j in range(num_detect):
                        # Verify traj. point lies within current spline interval
                        if self.visible[cam_id][j]:
                            timestamp = self.detections_global[cam_id][0,j]
                            _,_,traj_pnt = np.intersect1d(timestamp,self.global_traj[3],assume_unique=True,return_indices=True)
                            traj_pnt += traj_start

                            traj_idx = np.array([traj_pnt[0]])
                            if (traj_pnt-traj_start) < motion_offset:
                                traj_idx = np.arange(traj_start,traj_pnt+motion_offset) 
                                
                            else:
                                traj_idx = np.arange(traj_pnt-motion_offset,traj_pnt+motion_offset) 
                                
                            traj_idx = np.concatenate((traj_idx, traj_idx+traj_len, traj_idx+2*traj_len))
                            
                            if np.array(traj_idx < num_param).all():
                                jac_cam[j,traj_idx] = 1 
                            else:
                                jac_cam[j,traj_idx[traj_idx < num_param]] = 1         
                        else:
                            jac_cam[j] = 0
                        
                    jac = vstack((jac, vstack([jac_cam,jac_cam])))
                # Optimize Spline Params.    
                else:
                    # spline parameters
                    for j in range(num_detect):
                        spline_id = self.visible[cam_id][j]
                        # Find the corresponding spline for each detecion
                        if spline_id:
                            spline_id -= 1
                            knot = self.spline['tck'][spline_id][0][2:-2]
                            timestamp = self.detections_global[cam_id][0,j]
                            knot_idx = np.argsort(abs(knot-timestamp))[:near]
                            knot_idx = np.concatenate((knot_idx, knot_idx+len(knot), knot_idx+2*len(knot)))
                            jac_cam[j,idx_spline_sum[0,spline_id]+knot_idx] = 1
                        else:
                            jac_cam[j,:] = 0
                    
                    jac = vstack((jac, vstack([jac_cam,jac_cam])))
                    #jac = np.vstack((jac, np.tile(jac_cam,(2,1))))
                    
            if motion:
                m_jac = lil_matrix((self.global_traj.shape[1], num_param),dtype=int)
                traj_start = numCam * (3+num_camParam)
                for j in range(num_global_pnt):
                        m_jac[j] = 0
                        if j < motion_offset:
                           m_traj_idx = np.arange(0,j+motion_offset) 
                           m_traj_idx += traj_start#
                        else:
                            m_traj_idx = np.arange(j-motion_offset,j+motion_offset) 
                            m_traj_idx += traj_start
                        m_traj_idx = np.concatenate((m_traj_idx, m_traj_idx+traj_len, m_traj_idx+2*traj_len))
                        
                        if np.array(m_traj_idx < num_param).all():
                            m_jac[j,m_traj_idx] = 1
                        else:
                            m_jac[j,m_traj_idx[m_traj_idx < num_param]] = 1
                
                # fix the first camera
                # jac[:,[0,numCam]], jac[:,2*numCam+4:2*numCam+10] = 0, 0        
                
                jac = vstack((jac, m_jac))
                
            return jac.toarray()[1:]

        starttime = datetime.now()
        
        '''Before BA'''
        # Define Parameters that will be optimized
        model_alpha = self.alpha[self.sequence[:numCam]]
        model_beta = self.beta[self.sequence[:numCam]]
        model_rs = self.rs[self.sequence[:numCam]]

        model_cam = np.array([])
        num_camParam = 15 if self.settings['opt_calib'] else 6
        for i in self.sequence[:numCam]:
            model_cam = np.concatenate((model_cam, self.cameras[i].P2vector(calib=self.settings['opt_calib'])))
        model_other = np.concatenate((model_alpha, model_beta, model_rs, model_cam))
        
        if motion:
            #interpolate 3d points from detections in all cameras
            self.all_detect_to_traj(self.sequence[:numCam])
            model_traj = np.ravel(self.global_traj[4:].T)
            model = np.concatenate((model_other, model_traj))
        else:
            # Reorganized splines into 1D and record indices of each spline
            num_spline = len(self.spline['tck'])
            idx_spline = np.zeros((2,num_spline),dtype=int)
            start = 0
            model_spline = np.array([])
            for i in range(num_spline):
                model_spline_i = np.ravel(self.spline['tck'][i][1])
                model_spline = np.concatenate((model_spline, model_spline_i))
                end = start + len(model_spline_i)
                idx_spline[:,i] = [start,end]
                start = end
            idx_spline_sum = idx_spline + len(model_other)
            model = np.concatenate((model_other, model_spline))
            assert idx_spline_sum[-1,-1] == len(model), 'Wrong with spline indices'

        # Set the Jacobian matrix
        A = jac_BA(motion_offset=10)
        #A = None

        '''Compute BA'''
        print('Doing BA with {} cameras...\n'.format(numCam))
        fn = lambda x: error_BA(x)
        res = least_squares(fn,model,jac_sparsity=A,tr_solver='lsmr',max_nfev=max_iter,xtol=1e-12,verbose=2)

        '''After BA'''
        # Assign the optimized model to alpha, beta, cam, and spline
        sections = [numCam, numCam*2, numCam*3, numCam*3+numCam*num_camParam]
        model_parts = np.split(res.x, sections)
        self.alpha[self.sequence[:numCam]], self.beta[self.sequence[:numCam]], self.rs[self.sequence[:numCam]] = model_parts[0], model_parts[1], model_parts[2]

        cams = np.split(model_parts[3],numCam)
        for i in range(numCam):
            self.cameras[self.sequence[i]].vector2P(cams[i], calib=self.settings['opt_calib']) 
        if motion:
            self.global_traj[4:] = model_parts[4].reshape(-1,3).T
            if (self.global_traj[3][1:]>self.global_traj[3][:-1]).all():
                self.traj_to_spline()
            else:
                self.traj = self.global_traj[3:,np.argsort(self.global_traj[3,:])] #np.vstack((global_time_stamps_all[traj_idx],self.traj[1:]))
                self.traj_to_spline()
        else:
            spline_parts = np.split(model_parts[4],idx_spline[0,1:])
            for i in range(len(spline_parts)):
                spline_i = spline_parts[i].reshape(3,-1)
                self.spline['tck'][i][1] = [spline_i[0],spline_i[1],spline_i[2]]

        # Update global timestamps for each series of detections
        self.detection_to_global()

        return res
    
    def BA_mot(self, numCam, max_iter=10, rs=False,motion=False,motion_weights=100):
        '''
        Bundle Adjustment with multiple splines

        The camera order is assumed to be the same as self.sequence
        '''

        def error_BA(x):
            '''
            Input is the model (parameters that need to be optimized)
            '''

            # Assign parameters to the class attributes
            sections = [numCam, numCam*2, numCam*3, numCam*3+numCam*num_camParam]
            model_parts = np.split(x, sections)
            self.alpha[self.sequence[:numCam]], self.beta[self.sequence[:numCam]], self.rs[self.sequence[:numCam]] = model_parts[0], model_parts[1],model_parts[2]
            
            cams = np.split(model_parts[3],numCam)
            for i in range(numCam):
                self.cameras[self.sequence[i]].vector2P(cams[i], calib=self.settings['opt_calib']) 
        
            if motion:
            #   self.detect_to_traj(self.sequence[:numCam])
                self.global_traj[4:] = model_parts[4].reshape(-1,3).T

            else:
                spline_parts = np.split(model_parts[4],idx_spline[0,1:])
                for i in range(len(spline_parts)):
                    spline_i = spline_parts[i].reshape(3,-1)
                    self.spline['tck'][i][1] = [spline_i[0],spline_i[1],spline_i[2]]
                
            # Compute errors
            error = np.array([])
            if motion:
                norm = False
            for i in range(numCam):
                norm = False
                error_each = self.error_cam(self.sequence[i], mode='each',motion=motion,norm=norm)
                error = np.concatenate((error, error_each))
            if motion:
                error_mot = self.error_cam_mot(self.sequence[:numCam],motion=motion,motion_weights=motion_weights)
                error = np.concatenate((error, error_mot))

            # Compute errors
            # error = np.array([])
            # for i in range(numCam):
            #     error_each = self.error_cam(self.sequence[i], mode='each')
            #     error = np.concatenate((error, error_each))

            return error


        # def jac_BA_orig(near=3):

        #     """
        #     jacobian for multi_spline object
        #     """

        #     num_param = len(model)
        #     self.compute_visibility()

        #     jac = np.empty([0,num_param])
        #     for i in range(numCam):
        #         cam_id = self.sequence[i]
        #         num_detect = self.detections[cam_id].shape[1]

        #         # consider only reprojection in x direction, which is the same in y direction
        #         jac_cam = np.zeros((num_detect, num_param))

        #         # alpha and beta
        #         jac_cam[:,[i,i+numCam]] = 1

        #         # rolling shutter
        #         if rs:
        #             jac_cam[:,i+numCam*2] = 1
        #         else:
        #             jac_cam[:,i+numCam*2] = 0

        #         # camera parameters
        #         start = 3*numCam+i*self.cam_model
        #         jac_cam[:,start:start+self.cam_model] = 1

        #         # spline parameters
        #         for j in range(num_detect):
        #             spline_id = self.visible[cam_id][j]

        #             # Find the corresponding spline for each detecion
        #             if spline_id:
        #                 spline_id -= 1
        #                 knot = self.spline['tck'][spline_id][0][2:-2]
        #                 timestamp = self.detections_global[cam_id][0,j]
        #                 knot_idx = np.argsort(abs(knot-timestamp))[:near]
        #                 knot_idx = np.concatenate((knot_idx, knot_idx+len(knot), knot_idx+2*len(knot)))
        #                 jac_cam[j,idx_spline_sum[0,spline_id]+knot_idx] = 1
        #             else:
        #                 jac_cam[j,:] = 0

        #         jac = np.vstack((jac, np.tile(jac_cam,(2,1))))

        #     # fix the first camera
        #     # jac[:,[0,numCam]], jac[:,2*numCam+4:2*numCam+10] = 0, 0

        #     return jac

        def jac_BA(near=3):

            """
            compute jacobian for multi-spline object with possibility for motion prior optimization
            """

            num_param = len(model)
            self.compute_visibility()
            
            #if motion:
            jac = lil_matrix((1, num_param),dtype=int)
            #else:
            #    jac = np.empty([0,num_param])
            off_set = 500
            for i in range(numCam):
                cam_id = self.sequence[i]
                num_detect = self.detections[cam_id].shape[1]

                #if not motion:
                    # consider only reprojection in x direction, which is the same in y direction
                #jac_cam = np.zeros((num_detect, num_param))  
                jac_cam = lil_matrix((num_detect, num_param),dtype=int)
                if motion:
                    num_global_pnt = self.global_traj.shape[1]
                    #jac_cam = np.zeros((num_detect, num_param))
                    #jac_cam = lil_matrix((num_detect, num_param),dtype=int)
                    m_jac = lil_matrix((num_global_pnt, num_param),dtype=int)

                # alpha and beta
                jac_cam[:,[i,i+numCam]] = 1

                # rolling shutter
                if rs:
                    jac_cam[:,i+numCam*2] = 1
                else:
                    jac_cam[:,i+numCam*2] = 0

                # camera parameters
                start = 3*numCam+i*num_camParam
                jac_cam[:,start:start+num_camParam] = 1

                if motion:
                    traj_start = numCam * (3+num_camParam)
                    traj_len = self.global_traj.shape[1]
                    for j in range(num_detect):
                        spline_id = self.visible[cam_id][j]
                        # Find the corresponding spline for each detection
                        if spline_id:
                            #spline_id -= 1
                            #interval = self.spline['int'][:,spline_id]
                            timestamp = self.detections_global[cam_id][0,j]
                            _,_,idx2 = np.intersect1d(timestamp,self.global_traj[3],assume_unique=True,return_indices=True)
                            idx2 += traj_start

                            traj_idx = np.array([idx2[0]])
                            if (idx2-traj_start) < off_set:
                                traj_idx = np.arange(traj_start,idx2+off_set) 
                                
                            else:
                                traj_idx = np.arange(idx2-off_set,idx2+off_set) 
                                
                            traj_idx = np.concatenate((traj_idx, traj_idx+traj_len, traj_idx+2*traj_len))
                            
                            #m_traj_idx = np.array([idx2[0]-1,idx2[0],idx2[0]+1]) 
                            #m_traj_idx = np.concatenate((m_traj_idx, m_traj_idx+traj_len, m_traj_idx+2*traj_len))
                            
                            
                            #if traj_idx.all() < num_param:
                            #  jac_cam[j,traj_idx] = 1
                            if np.array(traj_idx < num_param).all():
                                jac_cam[j,traj_idx] = 1 
                            else:
                                jac_cam[j,traj_idx[traj_idx < num_param]] = 1
                            jac_cam[j,traj_start:] = 1
                            
                                
                        else:
                            jac_cam[j] = 0
                        
                    jac_X = jac_cam
                    jac_XY = vstack([jac_X,jac_cam])
            
                    #jac_X = vstack([jac_X,m_jac_cam])
                    #jac_X = vstack([jac_X,jac_cam])#.toarray()
                    #jac_X = jac_X.toarray()
                    jac = vstack((jac, jac_XY)) 
                else:
                    # spline parameters
                    for j in range(num_detect):
                        spline_id = self.visible[cam_id][j]
                        # Find the corresponding spline for each detecion
                        if spline_id:
                            spline_id -= 1
                            knot = self.spline['tck'][spline_id][0][2:-2]
                            timestamp = self.detections_global[cam_id][0,j]
                            knot_idx = np.argsort(abs(knot-timestamp))[:near]
                            knot_idx = np.concatenate((knot_idx, knot_idx+len(knot), knot_idx+2*len(knot)))
                            jac_cam[j,idx_spline_sum[0,spline_id]+knot_idx] = 1
                        else:
                            jac_cam[j,:] = 0
                    #if motion:
                    #    jac = np.vstack((jac, np.tile(jac_cam,(3,1))))
                    #else:
                    jac_X = jac_cam
                    jac_XY = vstack([jac_X,jac_cam])
                    jac = vstack((jac, jac_XY))
                    #jac = np.vstack((jac, np.tile(jac_cam,(2,1))))
                    
            # fix the first camera
            # jac[:,[0,numCam]], jac[:,2*numCam+4:2*numCam+10] = 0, 0
            if motion:
                traj_start = numCam * (3+num_camParam)
                for j in range(num_global_pnt):
                        m_jac[j] = 0
                        if j < off_set:
                           m_traj_idx = np.arange(0,j+off_set) 
                           m_traj_idx += traj_start#
                        else:
                            m_traj_idx = np.arange(j-off_set,j+off_set) 
                            m_traj_idx += traj_start
                            #np.array([j,j+1,j+2]) 
                        #m_traj_idx = np.array([j,j+1,j+2]) 
                        m_traj_idx = np.concatenate((m_traj_idx, m_traj_idx+traj_len, m_traj_idx+2*traj_len))
                        # Find the corresponding spline for each detection
                        if np.array(m_traj_idx < num_param).all():
                            m_jac[j,m_traj_idx] = 1
                        else:
                            m_jac[j,m_traj_idx[m_traj_idx < num_param]] = 1
                        m_jac[j,traj_start:] = 1
                #jac_X = vstack([jac_X,m_jac])
                jac = vstack((jac, m_jac)).toarray()
                return jac[1:]
            else:
                return jac.toarray()[1:]
        starttime = datetime.now()
        
        '''Before BA'''
        # Define Parameters that will be optimized
        model_alpha = self.alpha[self.sequence[:numCam]]
        model_beta = self.beta[self.sequence[:numCam]]
        model_rs = self.rs[self.sequence[:numCam]]

        model_cam = np.array([])
        num_camParam = 15 if self.settings['opt_calib'] else 6
        for i in self.sequence[:numCam]:
            model_cam = np.concatenate((model_cam, self.cameras[i].P2vector(calib=self.settings['opt_calib'])))
        model_other = np.concatenate((model_alpha, model_beta, model_rs, model_cam))
        
        #model_traj = np.array([])
        
        if motion:
            #interpolate 3d points from detections in all cameras
            self.all_detect_to_traj(self.sequence[:numCam])
            #self.spline_to_traj(t=np.sort(self.global_time_stamps_all))
        
           #_,idx,idx1 = np.intersect1d(self.traj[0],global_time_stamps_all,assume_unique=True,return_indices=True)
        
            # WIP
            #idx = np.isin(self.global_time_stamps_all,self.traj[0])
            #global_time_stamps_all = self.global_time_stamps_all[idx==True]
            #raw_time_stamps_all = self.raw_time_stamps_all[idx==True]
            #_,idx,idx1 = np.intersect1d(self.traj[0],global_time_stamps_all,assume_unique=True,return_indices=True)

            # Define a set of 3d points for each raw detection
            # raw_traj = np.empty([4,0])
            # for i,j in enumerate(raw_time_stamps_all):
            #     for k,l in enumerate(self.traj[0]):
            #         if global_time_stamps_all[i] == l:
            #             raw_traj = np.hstack((np.vstack((j,self.traj[1:,k].reshape(3,1))),raw_traj))
            #             break 
            #self.traj = raw_traj
            #model_traj_1 = np.empty([3,0])
            #model_traj = np.zeros((3,time_stamps_all.shape[0]))
            #model_traj = np.zeros((3,time_stamps_all.shape[0]))
            model_traj = np.ravel(self.global_traj[4:].T)
            
            # for i in self.sequence[:numCam]:
            #     temp_det = np.zeros((3,self.detections[i].shape[1]))
            #     #model_traj = np.concatenate((model_traj, temp_det))
            #     model_traj_1 = np.hstack((model_traj_1, temp_det))

            #model_traj[:,idx] = self.traj[1:] 
            model = np.concatenate((model_other, model_traj))

        else:
            # Reorganize splines into 1D and record indices of each spline
            num_spline = len(self.spline['tck'])
            idx_spline = np.zeros((2,num_spline),dtype=int)
            start = 0
            model_spline = np.array([])
            for i in range(num_spline):
                model_spline_i = np.ravel(self.spline['tck'][i][1])
                model_spline = np.concatenate((model_spline, model_spline_i))

                end = start + len(model_spline_i)
                idx_spline[:,i] = [start,end]
                start = end

            idx_spline_sum = idx_spline + len(model_other)
            model = np.concatenate((model_other, model_spline))
            assert idx_spline_sum[-1,-1] == len(model), 'Wrong with spline indices'

        # Set the Jacobian matrix
        #A = jac_BA()
        A = None

        '''Compute BA'''
        print('Doing BA with {} cameras...\n'.format(numCam))
        fn = lambda x: error_BA(x)
        res = least_squares(fn,model,jac_sparsity=A,tr_solver='lsmr',max_nfev=max_iter,verbose=2)

        '''After BA'''
        # Assign the optimized model to alpha, beta, cam, and spline
        sections = [numCam, numCam*2, numCam*3, numCam*3+numCam*num_camParam]
        model_parts = np.split(res.x, sections)
        self.alpha[self.sequence[:numCam]], self.beta[self.sequence[:numCam]], self.rs[self.sequence[:numCam]] = model_parts[0], model_parts[1], model_parts[2]

        cams = np.split(model_parts[3],numCam)
        for i in range(numCam):
            self.cameras[self.sequence[i]].vector2P(cams[i], calib=self.settings['opt_calib'])

        if motion:
            self.global_traj[4:] = model_parts[4].reshape(-1,3).T
            if len(self.global_traj[3].shape)==1 and (self.global_traj[3][1:]>self.global_traj[3][:-1]).all():
                self.traj_to_spline()
            else:
                #global_time_stamps_all = np.array([])
                #for i in range(numCam):
                #    self.detection_to_global(i)
                #    global_time_stamps_all = np.concatenate((global_time_stamps_all,self.detections_global[i][0]))
                #global_time_stamps_all = np.sort(global_time_stamps_all)
                #temp_global_traj = self.global_detections[:,np.argsort(self.global_detections[3,:])]
                self.traj = self.global_traj[3:,np.argsort(self.global_traj[3,:])] #np.vstack((global_time_stamps_all[traj_idx],self.traj[1:]))
                self.traj_to_spline()

        else:
            spline_parts = np.split(model_parts[4],idx_spline[0,1:])
            for i in range(len(spline_parts)):
                spline_i = spline_parts[i].reshape(3,-1)
                self.spline['tck'][i][1] = [spline_i[0],spline_i[1],spline_i[2]]

        # Update global timestamps for each series of detections
        self.detection_to_global()

        return res


    def remove_outliers(self, cams, thres=30, verbose=False):
        '''
        Not done yet!
        '''

        if thres:
            for i in cams:
                error_all = self.error_cam(i,mode='each')
                error_xy = np.split(error_all,2)
                error = np.sqrt(error_xy[0]**2 + error_xy[1]**2)

                self.detections[i] = self.detections[i][:,error<thres]
                self.detection_to_global(i)

                if verbose:
                    print('{} out of {} detections are removed for camera {}'.format(sum(error>=thres),sum(error!=0),i))


    def get_camera_pose(self, cam_id, error=8, verbose=0):
        '''
        Get the absolute pose of a camera by solving the PnP problem.

        Take care with DISTORSION model!
        '''
        
        tck, interval = self.spline['tck'], self.spline['int']
        self.detection_to_global(cam_id)

        _, idx = self.sampling(self.detections_global[cam_id], interval, belong=True)
        detect = np.empty([3,0])
        point_3D = np.empty([3,0])
        for i in range(interval.shape[1]):
            detect_part = self.detections_global[cam_id][:,idx==i+1]
            if detect_part.size:
                detect = np.hstack((detect,detect_part))
                point_3D = np.hstack((point_3D, np.asarray(interpolate.splev(detect_part[0], tck[i]))))

        # PnP solution from OpenCV
        N = point_3D.shape[1]
        objectPoints = np.ascontiguousarray(point_3D.T).reshape((N,1,3))
        imagePoints  = np.ascontiguousarray(detect[1:].T).reshape((N,1,2))
        distCoeffs = self.cameras[cam_id].d
        retval, rvec, tvec, inliers = cv2.solvePnPRansac(objectPoints, imagePoints, self.cameras[cam_id].K, distCoeffs, reprojectionError=error)

        self.cameras[cam_id].R = cv2.Rodrigues(rvec)[0]
        self.cameras[cam_id].t = tvec.reshape(-1,)
        self.cameras[cam_id].compose()

        if verbose:
            print('{} out of {} points are inliers for PnP'.format(inliers.shape[0], N))
            

    def triangulate(self, cam_id, cams, factor_t2s=0.001, factor_s2t=0.02, thres=0, refit=True, verbose=0):
        '''
        Triangulate new points to the existing 3D spline and optionally refit it

        cam_id is the new camera
        
        cams must be an iterable that contains cameras that have been processed to build the 3D spline
        '''

        assert self.cameras[cam_id].P is not None, 'The camera pose must be computed first'
        tck, interval = self.spline['tck'], self.spline['int']
        self.detection_to_global(cam_id)

        # Find detections from this camera that haven't been triangulated yet
        _, idx_ex = self.sampling(self.detections_global[cam_id], interval)
        detect_new = self.detections_global[cam_id][:, np.logical_not(idx_ex)]

        # Matching these detections with detections from previous cameras and triangulate them
        X_new = np.empty([4,0])
        for i in cams:
            self.detection_to_global(i)
            detect_ex = self.detections_global[i]

            # Detections of previous cameras are interpolated, no matter the fps
            try:
                x1, x2 = self.match_overlap(detect_new, detect_ex)
            except:
                continue
            else:
                P1, P2 = self.cameras[cam_id].P, self.cameras[i].P
                X_i = ep.triangulate_matlab(x1[1:], x2[1:], P1, P2)
                X_i = np.vstack((x1[0], X_i[:-1]))

                # Check reprojection error directly after triangulation, preserve those with small error
                if thres:
                    err_1 = ep.reprojection_error(x1[1:], self.cameras[cam_id].projectPoint(X_i[1:]))
                    err_2 = ep.reprojection_error(x2[1:], self.cameras[i].projectPoint(X_i[1:]))
                    mask = np.logical_and(err_1<thres, err_2<thres)
                    X_i = X_i[:, mask]
                    
                    if verbose:
                        print('{} out of {} points are triangulated'.format(sum(mask), len(err_1)))

                X_new = np.hstack((X_new, X_i))

                if verbose:
                    print('{} points are triangulated into the 3D spline'.format(X_i.shape[1]))

        _, idx_empty = self.sampling(X_new, interval)
        assert sum(idx_empty)==0, 'Points should not be triangulated into the existing part of the 3D spline'

        # Add these points to the discrete 3D trajectory
        self.spline_to_traj(sampling_rate=factor_s2t)
        self.traj = np.hstack((self.traj, X_new))
        _, idx = np.unique(self.traj[0], return_index=True)
        self.traj = self.traj[:, idx]

        # refit the 3D spline if wanted
        if refit:
            self.traj_to_spline(smooth_factor=factor_t2s)

        return X_new
        

    def plot_reprojection(self,interval=np.array([[-np.inf],[np.inf]]),match=True):
        '''
        Given temporal sections of the trajectory, plot the 2D reprojection of these sections for
        each possible camera
        '''

        assert interval.shape[0]==2

        for i in range(self.numCam):
            detect_i, _ = self.sampling(self.detections_global[i],interval)
            traj = self.spline_to_traj(t=detect_i[0])
            
            if traj.size:
                if match:
                    xy,x_ind,y_ind = np.intersect1d(detect_i[0],traj[0],assume_unique=True,return_indices=True)
                    detect_i = detect_i[:,x_ind]
                    traj = traj[:,y_ind]

                try:
                    repro = self.cameras[i].projectPoint(traj[1:])
                except:
                    continue
                
                plt.figure(figsize=(12, 10))
                plt.scatter(detect_i[1],detect_i[2],c='red')
                plt.scatter(repro[0],repro[1],c='blue')
                plt.xlabel('X')
                plt.ylabel('Y')
                plt.suptitle('Camera {}: undistorted detection (red) vs reporjection (blue)'.format(i))

        plt.show()


    def select_most_overlap(self,init=False):
        '''
        Select either the initial pair of cameras or the next best camera with largest overlap
        '''

        if not self.find_order:
            return

        self.detection_to_global()
        overlap_max = 0
        
        if init:
            for i in range(self.numCam-1):
                for j in range(i+1,self.numCam):
                    x, y = self.match_overlap(self.detections_global[i],self.detections_global[j])
                    overlap = x.shape[1] / self.cameras[i].fps
                    if overlap > overlap_max:
                        overlap_max = overlap
                        self.sequence = [i,j]
        else:
            traj = self.spline_to_traj()
            candidate = []
            for i in range(self.numCam):
                if self.cameras[i].P is None:
                    candidate.append(i)
            for i in candidate:
                interval = self.find_intervals(self.detections_global[i][0])
                overlap, _ = self.sampling(traj[0], interval)

                if len(overlap) > overlap_max:
                    overlap_max = len(overlap)
                    next_cam = i
            self.sequence.append(i)

    def all_detect_to_traj(self,*cam):
        #global_traj = np.empty()
        global_time_stamps_all = np.array([])
        frame_id_all = np.array([])
        cam_id = np.array([])

        if len(cam):
            for i in cam[0]:
                self.detection_to_global(i)
                global_time_stamps_all = np.concatenate((global_time_stamps_all,self.detections_global[i][0]))
                frame_id_all  = np.concatenate((frame_id_all,self.detections[i][0]))
                cam_id = np.concatenate((cam_id,np.ones(len(self.detections[i][0])) * i ))

        else:
            for i in range(self.numCam):
                self.detection_to_global(i)
                global_time_stamps_all = np.concatenate((global_time_stamps_all,self.detections_global[i][0]))
                frame_id_all = np.concatenate((frame_id_all,self.detections[i][0]))
                cam_id = np.concatenate((cam_id,np.ones(len(self.detections[i][0])) * i ))

        self.frame_id_all = frame_id_all 
        self.global_time_stamps_all = global_time_stamps_all
    
        # Interpolate 3D points for global timestamps in all cameras
        self.spline_to_traj(t=np.sort(global_time_stamps_all))
        
        self.global_detections = np.vstack((cam_id,frame_id_all,global_time_stamps_all))
        #self.global_traj = np.vstack((idx,cam_id,frame_id_all,global_time_stamps_all))
        #Sort global_traj by global time stamp
        temp_global_traj = self.global_detections[:,np.argsort(self.global_detections[2,:])]
        
        # Create ascending global timestamp trajectory
        _,traj_idx,_= np.intersect1d(temp_global_traj[2],self.traj[0],assume_unique=True,return_indices=True)
        temp_global_traj = np.vstack((temp_global_traj[:,traj_idx],self.traj[1:]))
        # Apply index to track original order of the global traj.
        temp_global_traj = np.vstack((np.arange(temp_global_traj.shape[1]),temp_global_traj))
        # Resort by global_traj idx to maintain original detection order
        #self.global_traj = temp_global_traj[:,np.argsort(temp_global_traj[0,:])]
        self.global_traj = temp_global_traj
        
        #verify global timestamps are sorted in ascending order
        assert (self.global_traj[3][1:]>self.global_traj[3][:-1]).all(), 'timestamps are not in ascending order'
        # # Plot timestamps for visualinspection
        # fig = plt.figure(figsize=(12, 10))
        # num = self.global_traj.shape[1]
        # ax = fig.add_subplot(1,1,1)
        # ax.scatter(np.arange(num),x[3])
        # #ax.scatter(np.arange(num),x[2]) #,c=np.arange(x[i].shape[1])*color)
        # plt.show()
        #vis.show_trajectory_3D(self.global_traj[4:],color=None)

        # # WIP
        # idx = np.isin(global_time_stamps_all,self.traj[0])
        # global_time_stamps_all = global_time_stamps_all[idx==True]
        # raw_time_stamps_all = raw_time_stamps_all[idx==True]
        # #_,idx,idx1 = np.intersect1d(self.traj[0],global_time_stamps_all,assume_unique=True,return_indices=True)

        # raw_traj = np.empty([4,0])
        # for i,j in enumerate(raw_time_stamps_all):
        #     for k,l in enumerate(self.traj[0]):
        #         if global_time_stamps_all[i] == l:
        #             raw_traj = np.hstack((np.vstack((j,self.traj[1:,k].reshape(3,1))),raw_traj))
        #             break 
    
        
        #_,idx,_ = np.intersect1d(global_time_stamps_all,self.traj[0],assume_unique=True,return_indices=True)
        #raw_traj = np.vstack((raw_time_stamps_all[idx],self.traj[1:]))
        #return raw_traj,idx

    def motion_prior(self,traj,weights,eps=1e-20,prior='F'):
        
        '''
        Function defining the physical motion constraint for the triangulated trajectory.

        inputs: 
        
        weighting: factor defined by the 2D reprojection uncertainty
        X: 3D point sequence

        returns: 
        Sm - cost function for physical motion prior
        
        '''
        assert traj.shape[0]==4, '3D points must be of shape 4 x n where row 0 is the time index'
        # Constant Kinetic Energy Motion Prior
        ts = traj[0]
        if prior == 'KE':
            
            traj_for = traj[1:,:-1]
            traj_aft = traj[1:,1:]
        
            #diff = norm((traj_aft[:,:] - traj_for[:,:])/((idx[1:]-idx[:-1])+eps),axis=0)
            vel = traj_aft[:,:] - traj_for[:,:]/((ts[1:]-ts[:-1])+eps)
            mot_resid = np.array([weights[:traj_for.shape[1]]*0.5*(vel**2 * (ts[1:]-ts[:-1]))])
        
        # Constant Force Motion Prior
        if prior == 'F':
            
            traj_for = traj[1:,:-2]
            traj_mid = traj[1:,1:-1]
            traj_aft = traj[1:,2:]

            dt1 = ts[1:-1] - ts[:-2]
            dt2 = ts[2:] - ts[1:-1]
            dt3 = ts[2:] - ts[:-2]

            v1 = (traj_mid - traj_for) / ( dt1 + eps)
            v2 = (traj_aft - traj_mid) / ( dt2 + eps )

            accel = (v2 - v1) / dt3
            mot_resid = np.array([weights[:traj_for.shape[1]]*(accel * (dt2 - dt1))])

        mot_resid = np.sum(abs(mot_resid[0]),axis=0)
        return mot_resid
        
class Camera:
    """ 
    Class that describes a single camera in the scene

    This class contains parameters of a single camera in the scene, i.e. its calibration parameters, pose parameters and its images
    
    Members
    -------
    K : calibration matrix
    R : camera orientation
    t : camera center
    d : distortion coefficients

    Methods
    -----
    projectPoint: get 2D coords from x=PX
    decompose: decompose P into K,R,t
    center: acquire 3D coords of the camera center

    """

    def __init__(self,**kwargs):
        self.P = kwargs.get('P')
        self.K = kwargs.get('K')
        self.R = kwargs.get('R')
        self.t = kwargs.get('t')
        self.d = kwargs.get('d')
        self.c = kwargs.get('c')
        self.fps = kwargs.get('fps')
        self.resolution = kwargs.get('resolution')


    def projectPoint(self,X):

        assert self.P is not None, 'The projection matrix P has not been calculated yet'
        if X.shape[0] == 3:
            X = util.homogeneous(X)
        x = np.dot(self.P,X)
        x /= x[2]
        return x


    def compose(self):
        self.P = np.dot(self.K,np.hstack((self.R,self.t.reshape((-1,1)))))


    def decompose(self):
        M = self.P[:,:3]
        R,K = np.linalg.qr(np.linalg.inv(M))
        R = np.linalg.inv(R)
        K = np.linalg.inv(K)

        T = np.diag(np.sign(np.diag(K)))
        if np.linalg.det(T) < 0:
            T[1,1] *= -1

        self.K = np.dot(K,T)
        self.R = np.dot(T,R)
        self.t = np.dot(np.linalg.inv(self.K),self.P[:,3])
        self.K /= self.K[-1,-1]

        return self.K, self.R, self.t


    def center(self):
        if self.c is not None:
            return self.c
        else:
            self.decompose()
            self.c = -np.dot(self.R.T,self.t)
            return self.c


    def P2vector(self, calib=False):
        '''
        Convert camera parameters into a vector
        '''

        k = np.array([self.K[0,0], self.K[1,1], self.K[0,2], self.K[1,2]])
        r = cv2.Rodrigues(self.R)[0].reshape(-1,)

        if calib:
            return np.concatenate((k, r, self.t, self.d))
        else:
            return np.concatenate((r,self.t))


    def vector2P(self, vector, calib=False):
        '''
        Convert a vector into camera parameters
        '''

        if calib:
            self.K = np.diag((1,1,1)).astype(float)
            self.K[0,0], self.K[1,1] = vector[0], vector[1]
            self.K[:2,-1] = vector[2:4]
            self.R = cv2.Rodrigues(vector[4:7])[0]
            self.t = vector[7:10]
            self.d = vector[10:15]
        else:
            self.R = cv2.Rodrigues(vector[:3])[0]
            self.t = vector[3:6]

        self.compose()
        return self.P
    

    def undist_point(self,points):
        
        assert points.shape[0]==2, 'Input must be a 2D array'

        num = points.shape[1]

        src = np.ascontiguousarray(points.T).reshape((num,1,2))
        dst = cv2.undistortPoints(src, self.K, self.d)
        dst_unnorm = np.dot(self.K, util.homogeneous(dst.reshape((num,2)).T))

        return dst_unnorm[:2]


    def info(self):
        print('\n P:')
        print(self.P)
        print('\n K:')
        print(self.K)
        print('\n R:')
        print(self.R)
        print('\n t:')
        print(self.t)


def create_scene(path_input):
    '''
    Create a scene from the imput template in json format
    '''

    # Read the config file
    with open(path_input, 'r') as file:
        config = json.load(file)

    # Create the scene
    flight = Scene()

    # Load settings
    flight.settings = config['settings']

    # Load detections
    path_detect = config['necessary inputs']['path_detections']
    flight.numCam = len(path_detect)
    for i in path_detect:
        detect = np.loadtxt(i,usecols=(2,0,1))[:flight.settings['num_detections']].T
        flight.addDetection(detect)

    # Load cameras, currently only work for opencv
    path_calib = config['necessary inputs']['path_calibration']
    fps = config['necessary inputs']['camera_fps']
    resolution = config['necessary inputs']['camera_resolution']

    if len(path_calib['opencv']):
        path_calib = path_calib['opencv']
        for i in range(flight.numCam):
            calib = np.load(path_calib[i])
            flight.addCamera(Camera(K=calib.f.mtx, d=calib.f.dist[0], fps=fps[i], resolution=resolution[i]))
    elif len(path_calib['matlab']):
        path_calib = path_calib['matlab']
    elif len(path_calib['txt']):
        path_calib = path_calib['txt']

    #  Load sequence
    flight.ref_cam = config['settings']['ref_cam']
    flight.sequence = config['settings']['camera_sequence']
    flight.find_order = False if len(flight.sequence) else True

    # Load time shifts
    flight.beta = np.asarray(config['optional inputs']['relative_time_shifts'])

    # Load rolling shutter parameter
    init_rs = config['settings']['init_rs'] if config['settings']['rolling_shutter'] else 0
    flight.rs = np.asarray([init_rs for i in range(flight.numCam)])

    # Load gps alignment parameter (optinal)
    flight.gps = {'alpha':config['optional inputs']['gps_alpha'], 'beta':config['optional inputs']['gps_beta']}

    print('Input data are loaded successfully, a scene is created.\n')
    return flight
