import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { axiosInstance } from '../../api/apiConfig'

export default function Register() {
    const navigate = useNavigate()
    const [loading, setLoading] = useState(false)
    const first_name = useRef()
    const last_name = useRef()
    const email = useRef()
    const password = useRef()
    const password2 = useRef(undefined)
    const wallet_address_eth = useRef()
    let [isNewWallet, setIsNewWallet] = useState(true);

    function onWalletBoxClick(event) {
        setIsNewWallet(!isNewWallet);
        console.log({ isNewWallet });
    }

    async function onSubmitForm(event) {
        event.preventDefault()
        let data = {
            first_name: first_name.current.value,
            last_name: last_name.current.value,
            email: email.current.value,
            password: password.current.value,
            password2: password2.current.value,
            is_new_wallet: isNewWallet,
        };
        if (wallet_address_eth.current !== null) {
            data.wallet_address_eth = wallet_address_eth.current.value;
        }

        setLoading(true)

        try {
            const response = await axiosInstance.post('auth/register', JSON.stringify(data))

            setLoading(false)

            navigate('/auth/login')
        } catch (error) {
            setLoading(false)
            // TODO: handle errors
        }
    }

    return (
        <div className='container'>
            <h2>Register</h2>
            <form onSubmit={onSubmitForm}>
                <div className="mb-3">
                    <input type="text" placeholder='First Name' autoComplete='off' className='form-control' id='first_name' ref={first_name} />
                </div>
                <div className="mb-3">
                    <input type="text" placeholder='Last Name' autoComplete='off' className='form-control' id='last_name' ref={last_name} />
                </div>
                <div className="mb-3">
                    <input type="email" placeholder='Email' autoComplete='off' className='form-control' id="email" ref={email} />
                </div>
                <div class="input-group mb-3">
                    <div class="input-group-prepend">
                        <div class="input-group-text">
                            <div class="custom-control custom-checkbox">
                                <input type="checkbox" class="custom-control-input"
                                    id="is_new_wallet" onClick={onWalletBoxClick}
                                    ariaLabel="Checkbox for following text input"
                                    defaultChecked={!isNewWallet} />
                            </div>
                        </div>
                    </div>
                    {isNewWallet
                        ? <label htmlFor='is_new_wallet' style={{ marginTop: 'auto', marginBottom: 'auto', marginLeft: '1rem' }} >I already have a wallet.</label>
                        : <input type="wallet_address_eth" placeholder='Your Ethereum wallet address'
                            autoComplete='off' className='form-control'
                            id="wallet_address_eth" ref={wallet_address_eth}
                            pattern="^0[xX][0-9a-fA-F]{40}$"
                            ariaLabel="Text input with checkbox" />
                    }
                </div>
                <div className="mb-3">
                    <input type="password" placeholder='Password' autoComplete='off' className='form-control' id="password" ref={password} />
                </div>
                <div className="mb-3">
                    <input type="password" placeholder='Confirm Password' autoComplete='off' className='form-control' id="passwordConfirmation" ref={password2} />
                </div>
                <div className="mb-3">
                    <button disabled={loading} className='btn btn-success' type="submit">Register</button>
                </div>
            </form>
        </div>
    )
}
