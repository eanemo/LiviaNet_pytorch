import numpy as np
import nibabel as nib
from sklearn.feature_extraction.image import extract_patches_2d as sk_extract_patches
import pdb
import itertools

def generate_indexes(patch_shape, expected_shape) :
    ndims = len(patch_shape)

    #poss_shape = [patch_shape[i+1] * (expected_shape[i] // patch_shape[i+1]) for i in range(ndims-1)]

    pad_shape = (9, 9, 3)
    poss_shape = [patch_shape[i + 1] * ((expected_shape[i] - pad_shape[i] * 2) // patch_shape[i + 1]) + pad_shape[i] * 2 for i in range(ndims - 1)]

    #idxs = [range(patch_shape[i+1], poss_shape[i] - patch_shape[i+1], patch_shape[i+1]) for i in range(ndims-1)]
    idxs = [range(pad_shape[i], poss_shape[i] - pad_shape[i], patch_shape[i + 1]) for i in range(ndims - 1)]
    #pdb.set_trace()
    return itertools.product(*idxs)

    
def extract_patches(volume, patch_shape, extraction_step) :
    #patches = sk_extract_patches(
    #    volume,
    #    patch_shape=patch_shape,
    #    extraction_step=extraction_step)

    #ndim = len(volume.shape)
    #npatches = np.prod(patches.shape[:ndim])

    #numPatches = 0
    patchesList = []
    for x_i in range(0,volume.shape[0]-patch_shape[0],extraction_step[0]):
        for y_i in range(0,volume.shape[1]-patch_shape[1],extraction_step[1]):
            for z_i in range(0,volume.shape[2]-patch_shape[2],extraction_step[2]):
                #print('{}:{} to {}:{} to {}:{}'.format(x_i,x_i+patch_shape[0],y_i,y_i+patch_shape[1],z_i,z_i+patch_shape[2]))

                patchesList.append(volume[x_i:x_i + patch_shape[0],
                                          y_i:y_i + patch_shape[1],
                                          z_i:z_i + patch_shape[2]])

    #pdb.set_trace()

    patches = np.concatenate(patchesList, axis=0)
    #return patches.reshape((npatches, ) + patch_shape)
    return patches.reshape((len(patchesList), ) + patch_shape)

# Double check that number of labels is continuous
def get_one_hot(targets, nb_classes):
    #return np.eye(nb_classes)[np.array(targets).reshape(-1)]
    return np.swapaxes(np.eye(nb_classes)[np.array(targets)],0,3) # Jose. To have the same shape as pytorch (batch_size, numclasses,x,y,z)

def build_set(imageData) :
    num_classes = 4
    patch_shape = (27, 27, 27)
    extraction_step=(5, 5, 5)

    label_selector = [slice(None)] + [slice(9, 18) for i in range(3)]

    # Extract patches from input volumes and ground truth
    imageData_1 = np.squeeze(imageData[0,:,:,:])
    imageData_g = np.squeeze(imageData[1,:,:,:])

    num_classes = len(np.unique(imageData_g))
    x = np.zeros((0, 3, 27, 27, 27))
    y = np.zeros((0, 9, 9, 9))

    #for idx in range(len(imageData)) :
    y_length = len(y)

    label_patches = extract_patches(imageData_g, patch_shape, extraction_step)
    label_patches = label_patches[label_selector]
    
    # Select only those who are important for processing
    valid_idxs = np.where(np.sum(label_patches, axis=(1, 2, 3)) != 0)

    # Filtering extracted patches
    label_patches = label_patches[valid_idxs]

    x = np.vstack((x, np.zeros((len(label_patches), 3, 27, 27, 27))))
    #y = np.vstack((y, np.zeros((len(label_patches), 9, 9, 9))))  # Jose

    y = label_patches
    del label_patches
    
    # Sampling strategy: reject samples which labels are only zeros
    T1_train = extract_patches(imageData_1, patch_shape, extraction_step)
    x[y_length:, 0, :, :, :] = T1_train[valid_idxs]
    del T1_train

    return x, y

def reconstruct_volume(patches, expected_shape) :
    patch_shape = patches.shape

    assert len(patch_shape) - 1 == len(expected_shape)

    reconstructed_img = np.zeros(expected_shape)

    for count, coord in enumerate(generate_indexes(patch_shape, expected_shape)) :
        selection = [slice(coord[i], coord[i] + patch_shape[i+1]) for i in range(len(coord))]

        reconstructed_img[selection] = patches[count]

    return reconstructed_img

def my_reconstruct_volume(patches, expected_shape, patch_shape, extraction_step) :
    reconstructed_img = np.zeros(expected_shape)
    idx = 0

    for x_i in range(0,expected_shape[0]-patch_shape[0],extraction_step[0]):
        for y_i in range(0,expected_shape[1]-patch_shape[1],extraction_step[1]):
            for z_i in range(0,expected_shape[2]-patch_shape[2],extraction_step[2]):
                reconstructed_img[(x_i + extraction_step[0]):(x_i + 2 * extraction_step[0]),
                                  (y_i + extraction_step[1]):(y_i + 2 * extraction_step[1]),
                                  (z_i + extraction_step[2]):(z_i + 2 * extraction_step[2])] = patches[idx]

                idx = idx + 1

    return reconstructed_img


def load_data_train(path1, pathg, imageNames, numSamples):

    samplesPerImage = int(numSamples/len(imageNames))
    #print(' - Extracting {} samples per image'.format(samplesPerImage))
    X_train = []
    Y_train = []
  
    for num in range(len(imageNames)):
        imageData_1 = nib.load(path1 + '/' + imageNames[num]).get_data()
        imageData_g = nib.load(pathg + '/' + imageNames[num]).get_data()
        
        num_classes = len(np.unique(imageData_g))

        imageData = np.stack((imageData_1, imageData_g))
        img_shape = imageData.shape

        x_train, y_train = build_set(imageData)
        idx = np.arange(x_train.shape[0])
        np.random.shuffle(idx)

        x_train = x_train[idx[:samplesPerImage],]
        y_train = y_train[idx[:samplesPerImage],]

        X_train.append(x_train)
        Y_train.append(y_train)

        del x_train
        del y_train

    X_train = np.asarray(X_train)
    Y_train = np.asarray(Y_train)

    X = np.concatenate(X_train, axis=0)
    del X_train

    Y = np.concatenate(Y_train, axis=0)
    del Y_train

    idx = np.arange(X.shape[0])
    np.random.shuffle(idx)

    return X[idx], Y[idx], img_shape


def load_data_test(path1, pathg, imgName):

    extraction_step_value = 9
    imageData_1 = nib.load(path1 + '/' + imgName).get_data()
    imageData_g = nib.load(pathg + '/' + imgName).get_data()

    imageData_1_new = np.zeros((imageData_1.shape[0],imageData_1.shape[1], imageData_1.shape[2] + 2*extraction_step_value))
    imageData_g_new = np.zeros((imageData_1.shape[0],imageData_1.shape[1], imageData_1.shape[2] + 2*extraction_step_value))

    imageData_1_new[:,:,extraction_step_value:extraction_step_value+imageData_1.shape[2]] = imageData_1
    imageData_g_new[:,:,extraction_step_value:extraction_step_value+imageData_g.shape[2]] = imageData_g

    num_classes = len(np.unique(imageData_g))
 
    imageData = np.stack((imageData_1_new, imageData_g_new))
    img_shape = imageData.shape

    patch_1 = extract_patches(imageData_1_new, patch_shape=(27, 27, 27), extraction_step=(9, 9, 9))
    patch_g = extract_patches(imageData_g_new, patch_shape=(27, 27, 27), extraction_step=(9, 9, 9))

    return patch_1, patch_g, img_shape
