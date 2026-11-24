#include "backend.h"
#include <QSettings>

Backend::Backend(const QByteArray &home, QObject *parent) : QObject(parent) { Q_UNUSED(home); }

void Backend::add() { ++m_count; QSettings().setValue("count", m_count); }

void Backend::_private_helper() {}
