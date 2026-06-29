from langdetect import detect, DetectorFactory
DetectorFactory.seed = 0
print("russian:", detect("привет мир"))
print("chinese:", detect("你好世界"))
print("mixed:", detect("hello مرحبا"))
