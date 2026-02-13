import logging
import base64
import numpy as np
import cv2
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class VisionAnalyzer:
    """
    Applies mathematical reasoning to visual inputs using YOLO (Quantitative) 
    and prepares context for Gemini (Qualitative).
    """

    def __init__(self, model_path: str = "yolov8n.pt"):
        """
        Initialize YOLO model.
        Args:
            model_path: Path to YOLO weights. Defaults to nano model (will download if missing).
        """
        try:
            logger.info(f"Loading YOLO model: {model_path}")
            # Lazy import to avoid startup lag
            from ultralytics import YOLO
            self.model = YOLO(model_path)
            
            # Color ranges in HSV
            # Note: OpenCV uses H: 0-179, S: 0-255, V: 0-255
            self.color_ranges = {
                "red1": ((0, 70, 50), (10, 255, 255)),
                "red2": ((170, 70, 50), (180, 255, 255)),
                "green": ((36, 70, 50), (89, 255, 255)),
                "blue": ((90, 70, 50), (128, 255, 255)),
                "yellow": ((20, 100, 100), (35, 255, 255)),
                "black": ((0, 0, 0), (180, 255, 30)),
                "white": ((0, 0, 200), (180, 50, 255)),
                "gray": ((0, 0, 50), (180, 50, 200))
            }

        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            self.model = None

    # Define aliases for Semantic Grounding
    ALIAS_MAP = {
        "sports ball": ["ball", "marble", "sphere", "globe", "orb"],
        "bottle": ["flask", "container", "vial"],
        "cup": ["mug", "glass", "tumbler"],
        "book": ["notebook", "textbook", "novel"],
        "vase": ["urn", "pot", "jar"] # Added vase for the marble misclassification
    }

    def get_canonical_name(self, detected_name: str, user_query: str) -> str:
        """
        Checks if the user's query mentions an alias for a detected object.
        """
        user_query_lower = user_query.lower()
        
        # If the detected name is in the query, keep it
        if detected_name in user_query_lower:
            return detected_name
            
        # Check aliases
        for canonical, aliases in self.ALIAS_MAP.items():
            if detected_name == canonical:
                for alias in aliases:
                    if alias in user_query_lower:
                        return alias # Return the word the user actually used
        
        return detected_name

    def _detect_color(self, roi: np.ndarray) -> str:
        """
        Detect dominant color in a Region of Interest (ROI).
        """
        if roi.size == 0:
            return "unknown"
            
        hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        max_pixels = 0
        dominant_color = "unknown"

        for color, (lower, upper) in self.color_ranges.items():
            mask = cv2.inRange(hsv_roi, np.array(lower), np.array(upper))
            count = cv2.countNonZero(mask)
            
            # Merit handling for split red ranges
            actual_color = "red" if "red" in color else color
            
            # Store counts? Simple max strategy for now
            if count > max_pixels:
                max_pixels = count
                dominant_color = actual_color
        
        return dominant_color

    def analyze(self, image_data: str, query: str = "") -> Dict[str, Any]:
        """
        Analyze the image.
        
        Args:
            image_data: Base64 encoded image string.
            query: User's query to determine intent (optional).
            
        Returns:
            Dict containing structured analysis results.
        """
        result = {
            "vision_mode": "qualitative", # Default to Gemini unless YOLO runs
            "quantitative_analysis": None,
            "status": "success"
        }

        if not self.model:
            return {"status": "error", "error": "Model not initialized"}

        # Heuristic: Only run YOLO if query implies counting/detection/quantification
        keywords = ["count", "how many", "number of", "calculate", "probability", "statistics", "quantify", "fraction", "percentage"]
        should_run_yolo = any(k in query.lower() for k in keywords) if query else True
        
        if not should_run_yolo:
            return result

        try:
            # Decode image
            img_bytes = base64.b64decode(image_data)
            nparr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                raise ValueError("Failed to decode image")

            # Run Interface
            results = self.model(img, verbose=False) 
            
            detections = {}
            confidences = []
            
            for r in results:
                for box in r.boxes:
                    # Confidence
                    conf = float(box.conf[0])
                    confidences.append(conf)
                    
                    # Class Name
                    cls_id = int(box.cls[0])
                    raw_class_name = self.model.names[cls_id]
                    class_name = self.get_canonical_name(raw_class_name, query)
                    
                    # Color Detection
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    # Clamp coordinates
                    h, w, _ = img.shape
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(w, x2), min(h, y2)
                    
                    roi = img[y1:y2, x1:x2]
                    color = self._detect_color(roi)
                    
                    # Key construction: e.g. "red_sports ball"
                    key = f"{color}_{class_name}"
                    
                    if key in detections:
                        detections[key] += 1
                    else:
                        detections[key] = 1
            
            if detections:
                total_objects = sum(detections.values())
                avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
                
                result["vision_mode"] = "quantitative"
                result["quantitative_analysis"] = {
                    "objects": detections,
                    "total_objects": total_objects,
                    "avg_confidence": round(avg_conf, 2)
                }
            else:
                 # YOLO ran but found nothing
                 result["vision_mode"] = "quantitative" # It still ran
                 result["quantitative_analysis"] = {
                    "objects": {},
                    "total_objects": 0,
                    "avg_confidence": 0.0
                }

        except Exception as e:
            logger.error(f"Vision Analysis failed: {e}")
            result["status"] = "error"
            result["error"] = str(e)
            
        return result
