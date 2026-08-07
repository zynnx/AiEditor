import random


class AIService:

    def analyze(self, video):

        print(f"Analyzing {video.filename}")

        return {
            "score": round(random.uniform(7.5, 10), 2),
            "best_moments": [
                {
                    "time": 45,
                    "reason": "Beautiful curve"
                },
                {
                    "time": 112,
                    "reason": "Mountain landscape"
                },
                {
                    "time": 185,
                    "reason": "Overtake"
                }
            ]
        }