import React, {Component} from "react";

import QRCode from "qrcode";

interface Props {
    shareOpens: any
    url:string
}

class ShareCanvas extends Component<Props, any> {
    constructor(props: any) {
        super(props);
    }

    public componentDidMount() {
        const canvas = document.getElementById('canvas')
        QRCode.toCanvas(canvas, this.props.url, (error: any) => {
            if (error) console.error(error)
        })
    }

    public preserve() {
        const img = document.getElementsByTagName('canvas')[0];
        const canvas = document.createElement('canvas');
        canvas.width = img.width;
        canvas.height = img.height;
        const myCanvas = canvas.getContext('2d') as any
        myCanvas.drawImage(img, 0, 0);
        const url = canvas.toDataURL('image/png');
        const downloadLink = document.getElementById('downloadLink') as any;
        downloadLink.setAttribute('href', url);
        downloadLink.setAttribute('download', '二维码.png');
        downloadLink.click();
    }

    public render() {
        return (
            <div className={'card-box'}>
                <div className={'card-left'}/>
                <div>
                    <canvas id="canvas"/>
                    <div className={'care-canvas-const'}>
                        <span style={{cursor: 'pointer', marginTop: '-10px'}}
                              onClick={this.preserve}>
                            保存
                            <a id="downloadLink"/>
                        </span>
                    </div>
                </div>
            </div>
        );
    }
}

export default ShareCanvas


// WEBPACK FOOTER //
// ./src/components/Share/ShareCanvas.tsx