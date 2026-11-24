QT += core gui qml quick
CONFIG += c++20
TARGET = tally
TEMPLATE = app

SOURCES += src/main.cpp src/backend.cpp
HEADERS += src/backend.h
RESOURCES += src/qml.qrc
