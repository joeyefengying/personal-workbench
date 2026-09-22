import { Button } from 'antd';
import React, { Component } from 'react';
import { InjectedIntlProps, injectIntl } from 'react-intl';
import { connect, Dispatch } from 'react-redux';
import ClientVersionForm from '../../api/models/ClientVersionModel';
import RequestState from '../../constants/RequestState';
import ClientVersionBO from '../../models/bo/ClientVersionBO';
import * as Action from './action';
import './index.scss';

interface Props {
  requestState: RequestState;
  version: ClientVersionBO;
  fetchClientVersion: (param: ClientVersionForm) => void;
}

class ClientVersion extends Component<Props & InjectedIntlProps> {
  constructor(props: Props & InjectedIntlProps) {
    super(props);

    this.fetchClientVersion = this.fetchClientVersion.bind(this);
  }

  public render() {
    return (
      <div className="client-version">
        <p>Feature Client Version</p>
        <Button
          type="primary"
          loading={this.props.requestState === RequestState.PENDING}
          onClick={this.fetchClientVersion}
        >
          获取最新版本
        </Button>
        <p>
          <span>最新版本：{this.props.version.latestVersion}</span>
        </p>
      </div>
    );
  }

  private fetchClientVersion() {
    this.props.fetchClientVersion({
      clientType: 'web',
      webVersion: 40000,
    });
  }
}

function mapStateToProps(state: any) {
  return {
    requestState: state.clientVersion.get('requestState'),
    version: state.clientVersion.get('version').toJS(),
  };
}

function mapDispatchToProps(dispatch: Dispatch<any>) {
  return {
    fetchClientVersion(form: ClientVersionForm) {
      dispatch(Action.fetchClientVersion(form));
    },
  };
}

export default connect(mapStateToProps, mapDispatchToProps)(injectIntl(ClientVersion));



// WEBPACK FOOTER //
// ./src/features/ClientVersion/index.tsx