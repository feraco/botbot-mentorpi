'use client';

import { useCallback, useRef } from 'react';
import { useRobotConnection } from '@/contexts/RobotConnectionContext';
import { useRobotProfile } from '@/contexts/RobotProfileContext';
import { useNotifications } from '@/contexts/NotificationsContext';
import * as ROSLIB from 'roslib';

interface MappingDatabase {
  name: string;
  path: string;
  size?: string;
  lastModified?: string;
}

interface ServiceResponse {
  success: boolean;
  message: string;
  db_files?: string[];
}

export function useRosMappingServices() {
  const { connection, connectionStatus } = useRobotConnection();
  const { currentProfile } = useRobotProfile();
  const { dispatch } = useNotifications();
  const ros = connection.ros;
  const isConnected = connectionStatus === 'connected';
  const servicesRef = useRef<{ [key: string]: ROSLIB.Service<unknown, unknown> }>({});

  // Build the rtab_manager service prefix based on the robot's ROS namespace
  const rtabPrefix = currentProfile?.rosNamespace
    ? `/${currentProfile.rosNamespace}/rtab_manager`
    : '/rtab_manager';

  const addNotification = useCallback((notification: { type: 'success' | 'error' | 'info' | 'warning'; title: string; message: string }) => {
    dispatch({
      type: 'ADD_NOTIFICATION',
      payload: notification,
    });
  }, [dispatch]);

  const getService = useCallback((serviceName: string, serviceType: string) => {
    if (!ros || !isConnected) {
      throw new Error('ROS is not connected');
    }

    const key = `${serviceName}_${serviceType}`;
    if (!servicesRef.current[key]) {
      servicesRef.current[key] = new ROSLIB.Service({
        ros,
        name: serviceName,
        serviceType,
      });
    }
    return servicesRef.current[key];
  }, [ros, isConnected]);

  const listDatabaseFiles = useCallback(async (): Promise<string[]> => {
    try {
      const service = getService(
        `${rtabPrefix}/list_db_files`,
        'bot_localization_interfaces/srv/ListDbFiles'
      );

      return new Promise((resolve, reject) => {
        const request = {};

        service.callService(request, (res: unknown) => {
          const response = res as ServiceResponse;
          if (response.success) {
            resolve(response.db_files || []);
          } else {
            reject(new Error(response.message || 'Failed to list database files'));
          }
        }, (error: unknown) => {
          reject(new Error(String(error)));
        });
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to list maps';
      addNotification({
        type: 'error',
        title: 'List Maps Failed',
        message,
      });
      throw error;
    }
  }, [getService, addNotification, rtabPrefix]);

  const loadDatabase = useCallback(async (databasePath: string, clearDb: boolean = false): Promise<void> => {
    try {
      const service = getService(
        `${rtabPrefix}/load_database`,
        'bot_localization_interfaces/srv/LoadDB'
      );

      return new Promise((resolve, reject) => {
        const request = {
          database_path: databasePath,
          clear_db: clearDb,
        };

        service.callService(request, (res: unknown) => {
          const response = res as ServiceResponse;
          if (response.success) {
            addNotification({
              type: 'success',
              title: 'Map Loaded',
              message: `Successfully loaded map: ${databasePath}`,
            });
            resolve();
          } else {
            reject(new Error(response.message || 'Failed to load database'));
          }
        }, (error: unknown) => {
          reject(new Error(String(error)));
        });
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to load map';
      addNotification({
        type: 'error',
        title: 'Load Map Failed',
        message,
      });
      throw error;
    }
  }, [getService, addNotification, rtabPrefix]);

  const setMappingMode = useCallback(async (databasePath?: string, clearDb: boolean = false): Promise<void> => {
    try {
      const service = getService(
        `${rtabPrefix}/set_mapping`,
        'bot_localization_interfaces/srv/SetMapping'
      );

      return new Promise((resolve, reject) => {
        const request = {
          database_path: databasePath || '',
          clear_db: clearDb,
        };

        service.callService(request, (res: unknown) => {
          const response = res as ServiceResponse;
          if (response.success) {
            const mapName = databasePath || 'current database';
            addNotification({
              type: 'success',
              title: 'Mapping Mode Started',
              message: `Now mapping with ${mapName}`,
            });
            resolve();
          } else {
            reject(new Error(response.message || 'Failed to set mapping mode'));
          }
        }, (error: unknown) => {
          reject(new Error(String(error)));
        });
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to start mapping';
      addNotification({
        type: 'error',
        title: 'Start Mapping Failed',
        message,
      });
      throw error;
    }
  }, [getService, addNotification, rtabPrefix]);

  const setLocalizationMode = useCallback(async (): Promise<void> => {
    try {
      const service = getService(
        `${rtabPrefix}/set_localization`,
        'bot_localization_interfaces/srv/SetLocalization'
      );

      return new Promise((resolve, reject) => {
        const request = {};

        service.callService(request, (res: unknown) => {
          const response = res as ServiceResponse;
          if (response.success) {
            addNotification({
              type: 'success',
              title: 'Localization Mode',
              message: 'Switched to localization mode',
            });
            resolve();
          } else {
            reject(new Error(response.message || 'Failed to set localization mode'));
          }
        }, (error: unknown) => {
          reject(new Error(String(error)));
        });
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to switch to localization';
      addNotification({
        type: 'error',
        title: 'Localization Failed',
        message,
      });
      throw error;
    }
  }, [getService, addNotification, rtabPrefix]);

  const saveDatabase = useCallback(async (): Promise<void> => {
    try {
      const service = getService(
        `${rtabPrefix}/save_database`,
        'bot_localization_interfaces/srv/SaveDatabase'
      );

      return new Promise((resolve, reject) => {
        const request = {};

        service.callService(request, (res: unknown) => {
          const response = res as ServiceResponse;
          if (response.success) {
            addNotification({
              type: 'success',
              title: 'Map Saved',
              message: 'Map has been saved successfully',
            });
            resolve();
          } else {
            reject(new Error(response.message || 'Failed to save database'));
          }
        }, (error: unknown) => {
          reject(new Error(String(error)));
        });
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to save map';
      addNotification({
        type: 'error',
        title: 'Save Map Failed',
        message,
      });
      throw error;
    }
  }, [getService, addNotification, rtabPrefix]);

  const deleteDatabase = useCallback(async (databasePath: string): Promise<void> => {
    try {
      const service = getService(
        `${rtabPrefix}/delete_database`,
        'bot_localization_interfaces/srv/DeleteDB'
      );

      return new Promise((resolve, reject) => {
        const request = {
          database_path: databasePath,
        };

        service.callService(request, (res: unknown) => {
          const response = res as ServiceResponse;
          if (response.success) {
            addNotification({
              type: 'success',
              title: 'Map Deleted',
              message: `Successfully deleted map: ${databasePath}`,
            });
            resolve();
          } else {
            reject(new Error(response.message || 'Failed to delete database'));
          }
        }, (error: unknown) => {
          reject(new Error(String(error)));
        });
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to delete map';
      addNotification({
        type: 'error',
        title: 'Delete Map Failed',
        message,
      });
      throw error;
    }
  }, [getService, addNotification, rtabPrefix]);

  const getCurrentDatabase = useCallback(async (): Promise<string | null> => {
    try {
      const service = getService(
        `${rtabPrefix}/get_current_database`,
        'std_srvs/srv/Trigger'
      );

      return new Promise((resolve) => {
        service.callService({}, (res: unknown) => {
          const response = res as { success: boolean; message: string };
          if (response.success) {
            // message contains the database name/path
            resolve(response.message || null);
          } else {
            resolve(null); // No active database, not an error
          }
        }, (error: unknown) => {
          // Service unavailable - resolve null (no active map)
          console.warn('get_current_database service unavailable:', error);
          resolve(null);
        });
      });
    } catch {
      return null;
    }
  }, [getService, rtabPrefix]);

  const formatDatabaseInfo = useCallback((dbFiles: string[]): MappingDatabase[] => {
    return dbFiles.map(file => ({
      name: file.replace('.db', ''),
      path: file,
      size: 'Unknown',
      lastModified: 'Unknown',
    }));
  }, []);

  /**
   * Start or stop the autonomous exploration node.
   * Calls /robotdog/exploration_control (std_srvs/SetBool).
   */
  const explorationControl = useCallback(async (enable: boolean): Promise<boolean> => {
    try {
      const prefix = currentProfile?.rosNamespace
        ? `/${currentProfile.rosNamespace}`
        : '';
      const service = getService(
        `${prefix}/exploration_control`,
        'std_srvs/SetBool',
      );
      return new Promise((resolve) => {
        service.callService(
          { data: enable },
          (res: unknown) => {
            const response = res as { success: boolean; message: string };
            if (response.success) {
              addNotification({
                type: 'info',
                title: enable ? 'Exploration Started' : 'Exploration Stopped',
                message: response.message || (enable ? 'Robot is now exploring the room.' : 'Exploration stopped.'),
              });
            }
            resolve(response.success);
          },
          (error: unknown) => {
            addNotification({
              type: 'error',
              title: 'Exploration Error',
              message: String(error),
            });
            resolve(false);
          },
        );
      });
    } catch (error) {
      addNotification({
        type: 'error',
        title: 'Exploration Error',
        message: error instanceof Error ? error.message : 'Service unavailable',
      });
      return false;
    }
  }, [getService, currentProfile, addNotification]);

  return {
    isConnected,
    listDatabaseFiles,
    loadDatabase,
    setMappingMode,
    setLocalizationMode,
    saveDatabase,
    deleteDatabase,
    getCurrentDatabase,
    formatDatabaseInfo,
    explorationControl,
  };
}