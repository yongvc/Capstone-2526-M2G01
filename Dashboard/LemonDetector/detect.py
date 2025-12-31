import cv2
import numpy as np

class LemonDetector:
    def __init__(self, tuning_mode=False):
        self.tuning_mode = tuning_mode
        self.window_name = "Tuning"
        
        # Fixed values
        self.FIXED_H_MIN = 20
        self.FIXED_H_MAX = 35
        self.FIXED_S_MIN = 50
        self.FIXED_S_MAX = 255
        self.FIXED_V_MIN = 100
        self.FIXED_V_MAX = 255
        self.FIXED_SEP_THRESH = 10 # 0-100
        self.MIN_CIRCULARITY = 0.3


        if self.tuning_mode:
            self._create_trackbars()
            
        # Tracking State
        self.nextObjectID = 0
        self.objects = {}      # ID -> (x, y)
        self.disappeared = {}  # ID -> frames_lost
        self.maxDisappeared = 1000 # frames

    def _nothing(self, x):
        pass

    def _create_trackbars(self):
        cv2.namedWindow(self.window_name)
        cv2.resizeWindow(self.window_name, 600, 300)

        # create trackbars for color change
        cv2.createTrackbar('H Min', self.window_name, self.FIXED_H_MIN, 179, self._nothing)
        cv2.createTrackbar('H Max', self.window_name, self.FIXED_H_MAX, 179, self._nothing)
        cv2.createTrackbar('S Min', self.window_name, self.FIXED_S_MIN, 255, self._nothing)
        cv2.createTrackbar('S Max', self.window_name, self.FIXED_S_MAX, 255, self._nothing)
        cv2.createTrackbar('V Min', self.window_name, self.FIXED_V_MIN, 255, self._nothing)
        cv2.createTrackbar('V Max', self.window_name, self.FIXED_V_MAX, 255, self._nothing)
        
        # Trackbar for distance transform threshold
        cv2.createTrackbar('Sep Thresh', self.window_name, self.FIXED_SEP_THRESH, 99, self._nothing)

    def _get_hsv_ranges(self):
        if self.tuning_mode:
            h_min = cv2.getTrackbarPos('H Min', self.window_name)
            h_max = cv2.getTrackbarPos('H Max', self.window_name)
            s_min = cv2.getTrackbarPos('S Min', self.window_name)
            s_max = cv2.getTrackbarPos('S Max', self.window_name)
            v_min = cv2.getTrackbarPos('V Min', self.window_name)
            v_max = cv2.getTrackbarPos('V Max', self.window_name)
            sep_thresh_val = cv2.getTrackbarPos('Sep Thresh', self.window_name) / 100.0
        else:
            h_min = self.FIXED_H_MIN
            h_max = self.FIXED_H_MAX
            s_min = self.FIXED_S_MIN
            s_max = self.FIXED_S_MAX
            v_min = self.FIXED_V_MIN
            v_max = self.FIXED_V_MAX
            sep_thresh_val = self.FIXED_SEP_THRESH / 100.0
            
        # Ensure min < max
        if h_min > h_max: h_max = h_min
        if s_min > s_max: s_max = s_min
        if v_min > v_max: v_max = v_min

        return (np.array([h_min, s_min, v_min]), 
                np.array([h_max, s_max, v_max]), 
                sep_thresh_val)

    def detect(self, frame):
        """
        Detects lemons in the given frame.
        Returns:
            result_frame: Frame with visualized detections.
            lemons: List of detected lemons sorted by distance to center.
        """
        # 1. Pre-processing
        blurred = cv2.GaussianBlur(frame, (11, 11), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

        # 2. Get values
        lower_hsv, upper_hsv, sep_thresh_val = self._get_hsv_ranges()

        # 3. Thresholding
        mask = cv2.inRange(hsv, lower_hsv, upper_hsv)

        # 4. Morphology
        kernel = np.ones((3,3), np.uint8)
        opening = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)
        sure_bg = cv2.dilate(opening, kernel, iterations=3)

        # 5. Watershed
        dist_transform = cv2.distanceTransform(opening, cv2.DIST_L2, 5)
        dist_max = dist_transform.max()
        
        if dist_max > 0:
            ret, sure_fg = cv2.threshold(dist_transform, sep_thresh_val * dist_max, 255, 0)
        else:
            sure_fg = np.zeros_like(dist_transform)

        sure_fg = np.uint8(sure_fg)
        unknown = cv2.subtract(sure_bg, sure_fg)

        ret, markers = cv2.connectedComponents(sure_fg)
        markers = markers + 1
        markers[unknown == 255] = 0

        markers = cv2.watershed(blurred, markers)
        
        # 6. Analysis
        result_frame = frame.copy()
        unique_labels = np.unique(markers)
        
        lemons = []
        height, width = frame.shape[:2]
        center_x, center_y = width // 2, height // 2

        for label in unique_labels:
            if label == 0 or label == 1:
                continue

            label_mask = np.zeros(mask.shape, dtype="uint8")
            label_mask[markers == label] = 255

            cnts, _ = cv2.findContours(label_mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if len(cnts) > 0:
                c = max(cnts, key=cv2.contourArea)
                area = cv2.contourArea(c)
                
                # Filter small noise
                if area < 1000: 
                    continue

                # Filter objects that are too large
                if area > (width * height) * 0.90:
                    continue

                # Filter by circularity
                perimeter = cv2.arcLength(c, True)
                if perimeter == 0:
                    continue
                circularity = 4 * np.pi * area / (perimeter * perimeter)
                if circularity < self.MIN_CIRCULARITY:
                    continue


                # Get centroid
                M = cv2.moments(c)
                if M["m00"] != 0:
                    cX = int(M["m10"] / M["m00"])
                    cY = int(M["m01"] / M["m00"])
                else:
                    cX, cY = 0, 0

                # Visualization
                cv2.drawContours(result_frame, [c], -1, (0, 255, 0), 2)
                cv2.circle(result_frame, (cX, cY), 5, (255, 0, 0), -1)
                
                label_text = f"Area: {int(area)}"
                coord_text = f"({cX}, {cY})"
                
                cv2.putText(result_frame, label_text, (cX - 20, cY - 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                cv2.putText(result_frame, coord_text, (cX - 20, cY + 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                
                # Data collection
                dist_to_center = ((cX - center_x)**2 + (cY - center_y)**2)**0.5
                
                lemons.append({
                    "x": cX,
                    "y": cY,
                    "area": int(area),
                    "dist": dist_to_center
                }) 

        # Sort
        lemons.sort(key=lambda x: x["dist"])
        
        # ================= TRACKING LOGIC =================
        # Extract centroids from current frame
        inputCentroids = [(l["x"], l["y"]) for l in lemons]

        # If no objects are currently tracked
        if len(self.objects) == 0:
            for i in range(0, len(inputCentroids)):
                self.register(inputCentroids[i])
        
        # If we have tracked objects but no new detections
        elif len(inputCentroids) == 0:
            for objectID in list(self.disappeared.keys()):
                self.disappeared[objectID] += 1
                if self.disappeared[objectID] > self.maxDisappeared:
                    self.deregister(objectID)
            # Return existing objects marked as disappeared? 
            # For now, if no detections, we just return empty list or last known positions?
            # The user wants "if some frame lost track, does not change target". 
            # So we should maintain the list.
            pass

        # We have both existing objects and new detections
        else:
            objectIDs = list(self.objects.keys())
            objectCentroids = list(self.objects.values())

            # Calculate distance between each pair of existing and new centroids
            # Using simple Euclidean distance
            D = []
            for i in range(len(objectCentroids)):
                row = []
                for j in range(len(inputCentroids)):
                    dist = ((objectCentroids[i][0] - inputCentroids[j][0]) ** 2 + 
                            (objectCentroids[i][1] - inputCentroids[j][1]) ** 2) ** 0.5
                    row.append(dist)
                D.append(row)
            D = np.array(D)

            # Find smallest value in each row (for each existing object)
            rows = D.min(axis=1).argsort()
            # Find smallest value in each col (for each new input)
            cols = D.argmin(axis=1)[rows]

            usedRows = set()
            usedCols = set()

            for (row, col) in zip(rows, cols):
                if row in usedRows or col in usedCols:
                    continue
                
                # If distance is too large, don't match
                if D[row][col] > 50: # max distance to match
                    continue

                objectID = objectIDs[row]
                self.objects[objectID] = inputCentroids[col]
                self.disappeared[objectID] = 0
                
                usedRows.add(row)
                usedCols.add(col)

            # unexpected disappearances
            unusedRows = set(range(0, D.shape[0])).difference(usedRows)
            for row in unusedRows:
                objectID = objectIDs[row]
                self.disappeared[objectID] += 1
                if self.disappeared[objectID] > self.maxDisappeared:
                    self.deregister(objectID)

            # unexpected new appearances
            unusedCols = set(range(0, D.shape[1])).difference(usedCols)
            for col in unusedCols:
                self.register(inputCentroids[col])

        # Attach IDs to the lemon list and Draw
        # We need to map back the inputCentroids to the objectIDs
        # This is strictly for "current frame detections" that were matched.
        # However, we also might want to show "Predicted" positions for lost objects.
        # For simplicity, let's just add the ID to the lemon dict if it matches a tracked object.
        
        # Re-iterate lemons to add ID
        final_lemons = []
        for l in lemons:
            cx, cy = l["x"], l["y"]
            # Find which objectID has this centroid
            matched_id = None
            for objID, (ox, oy) in self.objects.items():
                if ox == cx and oy == cy:
                    matched_id = objID
                    break
            
            if matched_id is not None:
                l["id"] = matched_id
                final_lemons.append(l)
                
                # Draw ID
                cv2.putText(result_frame, f"ID {matched_id}", (l["x"], l["y"]),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        
        # Sort again by distance? They are already sorted by distance, but IDs might be mixed.
        # The user wanted a list, ranking by dist close to camera center.
        # final_lemons preserves the order of 'lemons' which was already sorted.
        
        # Show mask if tuning (optional)
        if self.tuning_mode:
            cv2.imshow('Mask', mask)
            
        return result_frame, final_lemons

    def register(self, centroid):
        self.objects[self.nextObjectID] = centroid
        self.disappeared[self.nextObjectID] = 0
        self.nextObjectID += 1

    def deregister(self, objectID):
        del self.objects[objectID]
        del self.disappeared[objectID]

def main():
    # Configuration
    TUNING_MODE = False
    
    cap = cv2.VideoCapture(0)
    detector = LemonDetector(tuning_mode=TUNING_MODE)

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame")
            break

        result_frame, lemons = detector.detect(frame)
        
        cv2.imshow('Original', result_frame)

        if len(lemons) > 0:
            print(f"Detected {len(lemons)} lemons: {lemons}")

        key = cv2.waitKey(1)
        if key == 27: # ESC
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
