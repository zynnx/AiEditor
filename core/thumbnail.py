import cv2


class ThumbnailGenerator:

    @staticmethod
    def get_frame(video_path: str):

        cap = cv2.VideoCapture(video_path)

        if not cap.isOpened():
            return None

        success, frame = cap.read()

        cap.release()

        if not success:
            return None

        return frame