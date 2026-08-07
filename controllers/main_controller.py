from services.video_service import VideoService
from services.ai_service import AIService


class MainController:

    def __init__(self):

        self.video = None
        self.ai = AIService()
  

    def open_video(self, filename: str):

        self.video = VideoService.load(filename)

        return self.video