import React, {Component} from "react";

interface Props {
    shareOpens:any;
    gmtExpire:any;
}

export class GmtExpire extends Component<Props>{
    constructor(props:any) {
        super(props);
    }

    public render() {
        return (
            <div style={{color:'#AAAFB5',margin:'3px 0px -13px 93px',height:'22px'}}>
                < div style={this.props.shareOpens.expireType===4?{display:'none'}:{display:'block'}}>
                    链接与二维码将在
                    <span style={{color:'#0161FF'}}> {this.props.gmtExpire} </span>
                    失效
                </div>
            </div>
        );
    }
}


// WEBPACK FOOTER //
// ./src/components/Share/GmtExpire.tsx