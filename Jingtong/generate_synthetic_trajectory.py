import numpy as np
from matplotlib import pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

def mapminmax(x,ymin,ymax):
    return (ymax-ymin)*(x-min(x))/(max(x)-min(x)) + ymin


'''
Parameters
'''
time = 1000     # total time
dn = 5          # time interval to sample a point
dt = 0.1        # time interval for movement, not important due to rescaling later
filename = "data/Synthetic_Trajectory_generated.txt"

while True:
    # Define position(r), velocity(v), acceleration(a)
    r = np.zeros([3,time])
    v = np.ones([3,time])

    for t in range(1,time):
        a = np.random.randn(3)
        v[:,t] = v[:,t-1] + a*dt
        r[:,t] = r[:,t-1] + v[:,t-1]*dt + 0.5*a*dt**2

    # Random sampling
    idx_1 = np.array(range(0,time,dn))
    idx_2 = np.random.randint(dn-1, size=len(idx_1))
    idx = idx_1 + idx_2

    # Rescale into final data
    data = np.zeros([3,len(idx_1)])
    data[0] = mapminmax(r[0,idx],-5,5)
    data[1] = mapminmax(r[1,idx],-5,5)
    data[2] = mapminmax(r[2,idx],-5,5)

    # Show the 3D trajectory
    fig = plt.figure()
    ax = fig.gca(projection='3d')
    ax.scatter3D(data[0],data[1],data[2])
    plt.xlabel('x')
    plt.ylabel('y')
    plt.show()

    # Ask if the data is accepted
    print("\nDo you want to save this trajectory?")
    decision = input("Enter 'y' to save it, enter 'n' to regenerate, enter anyother key to exit: ")

    if decision == 'y':
        np.savetxt(filename, data, header="This is a synthetic trajectory dataset generated by generate_synthetic_trajectory.py")
        print('\nThe trajectory is saved under the name "Synthetic_Trajectory_generated.txt".\n')
        break
    elif decision == 'n':
        pass
    else:
        print('\nNo trajectory is generated')
        break