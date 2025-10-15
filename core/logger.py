# import logging

# # Configure file + console logging
# logging.basicConfig(
#     level=logging.DEBUG,  # keep DEBUG for your own modules
#     format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
#     handlers=[
#         logging.FileHandler("analysis.log", mode="a"),
#         logging.StreamHandler()
#     ]
# )

# logger = logging.getLogger("app")

# # Suppress noisy pymongo logs
# logging.getLogger("pymongo").setLevel(logging.WARNING)
# logging.getLogger("pymongo.topology").setLevel(logging.ERROR)
# logging.getLogger("pymongo.ocsp_support").setLevel(logging.ERROR)

# # Suppress noisy botocore + boto3 debug logs
# logging.getLogger("botocore").setLevel(logging.WARNING)
# logging.getLogger("boto3").setLevel(logging.WARNING)


import logging

# Configure file + console logging
logging.basicConfig(
    level=logging.DEBUG,  # keep DEBUG for your own modules
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("analysis.log", mode="a"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("app")

# Suppress noisy pymongo logs
logging.getLogger("pymongo").setLevel(logging.WARNING)
logging.getLogger("pymongo.topology").setLevel(logging.ERROR)
logging.getLogger("pymongo.ocsp_support").setLevel(logging.ERROR)

# Suppress noisy botocore + boto3 debug logs
logging.getLogger("botocore").setLevel(logging.WARNING)
logging.getLogger("boto3").setLevel(logging.WARNING)

# Suppress noisy matplotlib logs
logging.getLogger("matplotlib").setLevel(logging.WARNING)
logging.getLogger("matplotlib.font_manager").setLevel(logging.WARNING)

# Suppress noisy torch + torio logs
logging.getLogger("torch").setLevel(logging.WARNING)
logging.getLogger("torio").setLevel(logging.WARNING)
logging.getLogger("torio._extension.utils").setLevel(logging.WARNING)
