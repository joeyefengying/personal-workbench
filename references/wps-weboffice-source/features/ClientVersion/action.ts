import ClientVersionForm from '../../api/models/ClientVersionModel';
import ExceptionInfo from '../../exceptions/ExceptionInfo';
import ClientVersionBO from '../../models/bo/ClientVersionBO';
import {
  FETCH_CLIENT_VERSION_FAIL,
  FETCH_CLIENT_VERSION_REQUEST,
  FETCH_CLIENT_VERSION_SUCCESS,
} from './constants';

export interface FetchClientVersionRequest {
  type: FETCH_CLIENT_VERSION_REQUEST;
  payload: ClientVersionForm;
}

export interface FetchClientVersionFail {
  type: FETCH_CLIENT_VERSION_FAIL;
  payload: ExceptionInfo;
}

export interface FetchClientVersionSuccess {
  type: FETCH_CLIENT_VERSION_SUCCESS;
  payload: ClientVersionBO;
}

export function fetchClientVersion(param: ClientVersionForm): FetchClientVersionRequest {
  return {
    type: FETCH_CLIENT_VERSION_REQUEST,
    payload: param,
  };
}

export function fetchClientVersionFail(error: ExceptionInfo): FetchClientVersionFail {
  return {
    type: FETCH_CLIENT_VERSION_FAIL,
    payload: error,
  };
}

export function fetchClientVersionSuccess(version: ClientVersionBO): FetchClientVersionSuccess {
  return {
    type: FETCH_CLIENT_VERSION_SUCCESS,
    payload: version,
  };
}



// WEBPACK FOOTER //
// ./src/features/ClientVersion/action.ts