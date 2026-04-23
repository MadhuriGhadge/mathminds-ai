import cv2
import numpy as np
from ultralytics import YOLO
import base64
import logging

logger = logging.getLogger(__name__)

class YoloVisionAnalyzer:
    """
    Wrapper for ultralytics YOLOv8 inference.
    Processes images, extracts bounding boxes, and draws visual annotations.
    """
    def __init__(self, model_path: str = "yolov8n.pt"):
        # yolov8n.pt is the default nano model. 
        # When a custom equation detection model is trained, just pass the new .pt path here
        logger.info(f"Loading YOLO model: {model_path}")
        self.model = YOLO(model_path)
        logger.info("YOLO model loaded.")

    def process_image(self, image_bytes: bytes) -> dict:
        """
        Runs YOLO inference on raw image bytes.
        Returns the raw bounding box data and a base64 encoded image 
        with drawn bounding boxes.
        """
        try:
            # 1. Decode bytes into a cv2 NumPy array
            nparr = np.frombuffer(image_bytes, np.uint8)
            img_cv2 = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img_cv2 is None:
                raise ValueError("Could not decode image bytes into OpenCV format")

            # 2. Run inference
            # conf=0.25 to catch faint handwriting/math.
            results = self.model(img_cv2, conf=0.25)

            if not results:
                return {
                    "status": "success",
                    "bboxes": [],
                    "annotated_base64": None
                }

            result = results[0]

            # 3. Extract bounding box data
            boxes_data = []
            if result.boxes:
                for box in result.boxes:
                    coords = box.xyxy[0].tolist() # [x1, y1, x2, y2]
                    conf = float(box.conf[0])
                    class_id = int(box.cls[0])
                    label = result.names[class_id]
                    boxes_data.append({
                        "label": label,
                        "confidence": conf,
                        "bbox": coords
                    })

            # 4. Generate the visually annotated image array
            # .plot() applies rectangles and labels using Ultralytics' built-in UI
            annotated_img = result.plot()

            # 5. Encode the annotated image back to base64 for the frontend
            _, buffer = cv2.imencode(".png", annotated_img)
            annotated_b64 = base64.b64encode(buffer).decode("utf-8")

            return {
                "status": "success",
                "bboxes": boxes_data,
                "annotated_base64": annotated_b64,
                "object_count": len(boxes_data)
            }

        except Exception as e:
            logger.error(f"YOLO Inference Error: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
