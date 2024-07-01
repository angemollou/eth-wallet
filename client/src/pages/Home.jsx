import React, { useEffect, useContext, useState } from 'react'
import useAuth from '../hooks/useAuth'
import useUserList from '../hooks/useUserList';
import { AuthContext } from '../context/AuthContext';

export default function Home() {
    const { user } = useAuth();
    const { userList } = useContext(AuthContext);
    const getUsers = useUserList()
    const [page, setPage] = useState(1);

    useEffect(() => {
        getUsers()
        console.log({ user });
    }, [user])

    return (
        <div className='container mt-3'>
            <h2>
                <div className='row'>
                    <div className="mb-12">
                        {user?.email !== undefined ? 'List user Ethereum balance' : 'Please login first'}
                    </div>
                    <table class="table table-sm">
                        <thead>
                            <tr>
                                <th scope="col">#</th>
                                <th scope="col">First</th>
                                <th scope="col">Last</th>
                                <th scope="col">Balance</th>
                            </tr>
                        </thead>
                        <tbody>
                            {userList.map((item, i) =>
                                <tr key={i}>
                                    <th scope="row">{i}</th>
                                    <td>{item?.first_name}</td>
                                    <td>{item?.last_name}</td>
                                    <td>{item?.balance_eth} ETH</td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </h2>
        </div>
    )
}
