#pragma once
#include <QObject>

class Backend : public QObject {
    Q_OBJECT
public:
    explicit Backend(const QByteArray &home, QObject *parent = nullptr);
    Q_INVOKABLE void add();
private:
    void _private_helper();
    int m_count = 0;
};
