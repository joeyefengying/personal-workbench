import { Select } from 'antd';
import React, { Component } from 'react';
import { FormattedMessage, InjectedIntlProps, injectIntl } from 'react-intl';
import { connect, Dispatch } from 'react-redux';
import LanguageType from '../../constants/LanguageType';
import * as Action from './action';
import './index.scss';

const Option = Select.Option;

interface Props {
  currentLanguage: LanguageType;
  changeLanguage: (lang: LanguageType) => void;
}

class LanguageComponent extends Component<Props & InjectedIntlProps> {
  constructor(props: Props & InjectedIntlProps) {
    super(props);

    this.changeLanguage = this.changeLanguage.bind(this);
  }

  public render() {
    return (
      <div className="language">
        <p>Feature Language</p>
        <div>
          <FormattedMessage id="demo.switch_language" />
          <Select
            value={this.props.currentLanguage}
            onChange={this.changeLanguage}
            className="language-select"
          >
            <Option value={LanguageType.ZH}>中文</Option>
            <Option value={LanguageType.EN}>English</Option>
          </Select>
        </div>
      </div>
    );
  }

  private changeLanguage(lang: LanguageType) {
    this.props.changeLanguage(lang);
  }
}

function mapStateToProps(state: any) {
  return {
    currentLanguage: state.language,
  };
}

function mapDispatchToProps(dispatch: Dispatch<any>) {
  return {
    changeLanguage(lang: LanguageType) {
      dispatch(Action.changeLanguage(lang));
    },
  };
}

export default connect(mapStateToProps, mapDispatchToProps)(injectIntl(LanguageComponent));



// WEBPACK FOOTER //
// ./src/features/Language/index.tsx