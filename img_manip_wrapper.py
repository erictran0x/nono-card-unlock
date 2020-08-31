from skimage import io
import cv2
import numpy as np


def load_image(url):
    return cv2.cvtColor(io.imread(url), cv2.COLOR_RGBA2BGRA)


def remove_background(img):
    gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thres = cv2.threshold(gray_img, 255, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)  # Find all white space
    img_contours = cv2.findContours(thres, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)[-2]  # Find outlines
    mask = np.zeros(img.shape[:2], np.uint8)  # Generate mask
    for i in img_contours:
        cv2.drawContours(mask, [i], -1, 255, -1)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    img = cv2.bitwise_and(img, img, mask=mask)  # Set background transparent
    w, h, _ = img.shape
    for i in range(w):
        for j in range(h):
            b, g, r, a = img[i, j]
            if a == 0 and (b + g + r) != 0:  # If alpha is 0 but bgr is not 0
                img[i, j] = [b, g, r, 255]  # Cheap fix: just set alpha to 255
    return img


def get_stat_values(img):
    def valid_pixel(cb, cg, cr):
        return 100 <= int(cb) + int(cg) + int(cr) <= 600  # Only count "light" pixels
    w, h, _ = img.shape
    sb, sg, sr = [], [], []
    for i in range(w):
        for j in range(h):
            b, g, r, a = img[i, j]
            if a != 0 and valid_pixel(b, g, r):  # Add bgr values to lists if pixel is valid
                sb.append(b)
                sg.append(g)
                sr.append(r)
    ab = sum(sb) / len(sb) if len(sb) > 0 else 0  # Get average bgr values
    ag = sum(sg) / len(sg) if len(sg) > 0 else 0
    ar = sum(sr) / len(sr) if len(sr) > 0 else 0
    vb, vg, vr = 0, 0, 0
    for x in range(len(sb)):  # Get stddev bgr values
        vb += ((sb[x] - ab) ** 2) / len(sb)
        vg += ((sg[x] - ag) ** 2) / len(sg)
        vr += ((sr[x] - ar) ** 2) / len(sr)
    return ab, ag, ar, vb ** 0.5, vg ** 0.5, vr ** 0.5
